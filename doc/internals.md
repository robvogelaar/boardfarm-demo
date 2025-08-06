# Boardfarm Internals Documentation

## Connection Architecture

This document explains the internal workings of boardfarm connections, how they are established, and how to extend them with custom connection types.

## Connection Types

### 1. Telnet Connection vs Ser2net Connection

#### **TelnetConnection**
- **Purpose**: Direct network connection to any telnet server/service
- **Inheritance**: Inherits directly from `BoardfarmPexpect`
- **Use Case**: Connecting to network services that expose a telnet interface
- **Validation**: Looks for generic telnet connection messages:
  - `"Connected to {ip_addr}"`
  - `"Escape character is '^]'."`

#### **Ser2NetConnection**
- **Purpose**: Specifically designed for serial-to-network proxy connections
- **Inheritance**: Inherits from `TelnetConnection` (specialized telnet connection)
- **Use Case**: Accessing serial console ports (like UART/USB serial) over the network
- **Validation**: First validates telnet connection, then looks for ser2net-specific banner:
  - `"ser2net port.*{port}"` - confirming connection through ser2net daemon
- **Required Setup**: Needs ser2net daemon running on target host with `/etc/ser2net.conf`:
  ```
  6031:telnet:0:/dev/ttyUSB0:115200 NONE 1STOPBIT 8DATABITS XONXOFF banner max-connections=1
  ```
  This maps TCP port 6031 to serial device `/dev/ttyUSB0` at 115200 baud

#### **Key Insight: Ser2net = Telnet + Banner Validation**

Ser2NetConnection is essentially identical to TelnetConnection with one additional validation step:

```python
# TelnetConnection.login_to_server() - Only validates telnet connection
if self.expect([
    f"Connected to {self._ip_addr}",
    "Escape character is '^]'.",
    pexpect.TIMEOUT
], timeout=10):
    raise DeviceConnectionError(...)

# Ser2NetConnection.login_to_server() - Adds ser2net validation
super().login_to_server(password)  # First: Call parent's telnet validation

if self.expect([
    f"ser2net port.*{self._port}",  # Then: Check for ser2net banner
    pexpect.TIMEOUT
], timeout=10):
    raise DeviceConnectionError(...)
```

**Summary**: Both connections spawn the same telnet subprocess. The only difference is that Ser2NetConnection performs an additional check for the ser2net banner (e.g., `"ser2net port 6031"`), which confirms you're connecting through a ser2net daemon rather than directly to a telnet service. This validation is useful for ensuring you're properly bridged to a serial device.

### 2. Other Built-in Connection Types

- **ssh_connection / authenticated_ssh**: SSH connections for secure remote access
- **ldap_authenticated_serial**: Serial connections with LDAP authentication
- **local_cmd**: Direct local command execution without network

## Connection Flow

### Where Does Telnet Actually Run?

The telnet program is executed as a subprocess by the **pexpect** library. Here's the detailed flow:

1. **Connection Factory** (`connection_factory.py:51,67`):
   - For telnet: Creates `TelnetConnection` with `command="telnet"`
   - For ser2net: Creates `Ser2NetConnection` with `command="telnet"`

2. **BoardfarmPexpect Init** (`boardfarm_pexpect.py:87-95`):
   ```python
   super().__init__(
       command=command,  # "telnet"
       args=list(args),   # ["192.168.2.120", "6031", "root@RaspberryPi-Gateway"]
       ...
   )
   ```

3. **Pexpect Spawn** (`pexpect/pty_spawn.py:205`):
   - Calls `self._spawn(command, args)`
   - Builds full command: `telnet 192.168.2.120 6031`
   - Uses `which()` to find telnet executable path (e.g., `/usr/bin/telnet`)

4. **Process Creation** (`pexpect/pty_spawn.py:303-307`):
   ```python
   self.ptyproc = self._spawnpty(self.args, env=self.env, cwd=self.cwd)
   self.pid = self.ptyproc.pid
   self.child_fd = self.ptyproc.fd
   ```
   - Creates a pseudo-terminal (PTY)
   - Forks and executes `/usr/bin/telnet 192.168.2.120 6031`
   - Returns process ID and file descriptor for communication

5. **Telnet Process Running**:
   - Telnet runs as a child process
   - Boardfarm communicates via PTY read/write operations
   - All input/output goes through pexpect's expect/send methods

### Complete Call Flow for Ser2NetConnection

The following describes how a `Ser2NetConnection` is established when running tests:

```
1. Test Execution
   └── pytest --board-name=rpi_cpe_1 --inventory-config=inventory.json

2. Device Registration (conftest.py)
   └── boardfarm_add_devices() hook
       └── Maps "rpi_cpe" → RpiCpeDevice class

3. Environment Setup (boardfarm3/plugins/setup_environment.py)
   └── boardfarm_setup_env() hook
       └── Triggers boot hook sequence

4. Device Boot Hook (rpi_cpe_device.py:75-77)
   └── RpiCpeDevice.boardfarm_device_boot()
       └── self.connect_to_consoles()

5. Connection Factory Call (rpi_cpe_device.py:26-33)
   └── connection_factory(
         connection_type="ser2net",  # from inventory.json
         ip_addr="192.168.2.120",
         port="6031",
         shell_prompt="root@RaspberryPi-Gateway"
       )

6. Factory Dispatch (connection_factory.py:27-34)
   └── connection_dispatcher["ser2net"]
       └── _ser2net_param_parser()

7. Ser2NetConnection Creation (connection_factory.py:61-74)
   └── Returns new Ser2NetConnection instance

8. Login to Server (rpi_cpe_device.py:34)
   └── self._console.login_to_server()
       ├── TelnetConnection.login_to_server() [inherited]
       └── Validates ser2net banner

9. Device Ready
   └── Connection established, ready for test commands
```

### Key Files and Their Roles

- **inventory.json**: Defines device connection parameters
  ```json
  {
    "connection_type": "ser2net",
    "ip_addr": "192.168.2.120",
    "port": "6031"
  }
  ```

- **connection_factory.py**: Maps connection types to implementation classes
  - Location: `boardfarm3/lib/connection_factory.py`
  - Contains dispatcher dictionary and parameter parsers

- **Device Classes**: Implement connection logic
  - Call `connection_factory()` in boot hooks or connect methods
  - Handle device-specific initialization

## Adding Custom Connection Types

### Method 1: Function Wrapping (Project-Level)

You can add custom connection types without modifying boardfarm by wrapping the connection factory function:

```python
# In conftest.py
from lxd_connection import LXDConnection

def register_lxd_connection():
    """Register LXD connection type with boardfarm."""
    from boardfarm3.lib import connection_factory
    
    # Store the original connection_factory function
    original_factory = connection_factory.connection_factory
    
    # Create a wrapper that adds LXD support
    def patched_connection_factory(connection_type, connection_name, **kwargs):
        if connection_type == "lxd":
            return LXDConnection(
                name=connection_name,
                container_name=kwargs.get("container_name", "rdk-container"),
                lxd_endpoint=kwargs.get("lxd_endpoint", "https://127.0.0.1:8443"),
                shell_prompt=[kwargs.get("shell_prompt", "root@")],
                save_console_logs=kwargs.get("save_console_logs", False),
                cert_file=kwargs.get("cert_file"),
                key_file=kwargs.get("key_file"),
                trust_password=kwargs.get("trust_password"),
            )
        else:
            # Fallback to original factory for other connection types
            return original_factory(connection_type, connection_name, **kwargs)
    
    # Replace the connection_factory function with our patched version
    connection_factory.connection_factory = patched_connection_factory

def pytest_configure(config):
    """Configure pytest and register custom devices."""
    # Register LXD connection type
    register_lxd_connection()
    # ... rest of configuration
```

This approach works because Python allows function replacement at runtime. The wrapper intercepts calls for "lxd" connection type and delegates others to the original factory.

### Method 2: Contributing to Boardfarm (Package-Level)

To add a connection type to boardfarm itself:

1. Create connection class in `boardfarm3/lib/connections/`
2. Import in `connection_factory.py`
3. Add to `connection_dispatcher` dictionary
4. Submit as pull request to boardfarm repository

## Connection Class Requirements

All connection classes must:

1. **Inherit from BoardfarmPexpect** (directly or indirectly)
2. **Implement required methods**:
   - `__init__()`: Initialize connection parameters
   - `login_to_server()`: Establish connection
   - `execute_command()`: Run commands (optional, often inherited)
   - `close()`: Clean up connection

3. **Handle pexpect interaction**:
   - Set up spawn command
   - Manage prompt patterns
   - Handle expect/send operations

## Debugging Connections

### Common Issues

1. **Connection Timeout**: Check network connectivity and port accessibility
   ```bash
   telnet 192.168.2.120 6031  # Test ser2net connection
   ```

2. **Prompt Mismatch**: Ensure `shell_prompt` in inventory.json matches actual device prompt

3. **Ser2net Not Running**: Verify ser2net daemon status on host
   ```bash
   systemctl status ser2net
   ```

4. **Wrong Connection Type**: Verify `connection_type` in inventory.json matches your setup

### Useful Debug Commands

```python
# In your device class
print(f"Connecting with: {self._config}")
print(f"Connection type: {self._config.get('connection_type')}")
print(f"Console object: {self._console}")
```

## Architecture Decisions

### Why Connection Factory Pattern?

- **Centralized Creation**: Single point for all connection instantiation
- **Type Safety**: Validates connection types at runtime
- **Extensibility**: Easy to add new connection types
- **Configuration-Driven**: Connection details from JSON configs

### Why Inherit from BoardfarmPexpect?

- **Unified Interface**: Consistent API across all connections
- **Pexpect Integration**: Leverages robust expect/send functionality
- **Logging Support**: Built-in console logging capabilities
- **Async Support**: Optional async operations for modern workflows

## Best Practices

1. **Use Appropriate Connection Type**:
   - `ser2net` for serial consoles
   - `ssh_connection` for Linux servers
   - `telnet` for network equipment
   - Custom types for proprietary protocols

2. **Handle Connection Failures Gracefully**:
   - Implement retry logic if needed
   - Provide clear error messages
   - Clean up resources on failure

3. **Validate Connection Parameters**:
   - Check required fields exist
   - Validate IP addresses and ports
   - Verify prompt patterns match

4. **Log Connection Details**:
   - Use boardfarm's logging framework
   - Record connection attempts and failures
   - Save console output when debugging
