# Boardfarm CPE Demo

A getting started guide for pytest-boardfarm integration, demonstrating foundational device implementation concepts with Raspberry Pi based RDK CPE devices.

## Introduction

[Boardfarm](https://github.com/lgirdk/boardfarm) is a pytest plugin [pytest-boardfarm](https://github.com/lgirdk/pytest-boardfarm) for automated testing of network devices. **Production environments** include:

- **Comprehensive Device Support**: OEM-specific implementations, CMTS systems, provisioning servers, test infrastructure
- **Intelligent Test Orchestration**: Automatic device discovery, dynamic test filtering, adaptive execution based on available inventory
- **Use Case Driven Test Suites**: Real-world scenarios (WiFi onboarding, IPTV streaming, firmware upgrades) that adapt to any device combination
- **Scalable Architecture**: Protocol libraries, compliance suites, CI/CD pipelines with analytics

### This Demo

**⚠️ This demo covers only basic device implementation fundamentals** - the foundational layer upon which production boardfarm's sophisticated capabilities are built.

**Demo Scope**: Two implementation approaches:
1. **Simple** (`RpiCpeDevice`): Basic command execution
2. **Advanced** (`RdkCpeDevice`): Full template implementation with hardware/software separation

## Features

- **Simple RpiCpeDevice**: Basic shell command execution
- **Advanced RdkCpeDevice**: data model access support, networking features
- Pytest-boardfarm integration with device manager
- Automatic device registration via boardfarm hooks
- **Connection Methods**:
  - **ser2net**: Physical Raspberry Pi via serial-to-network proxy
  - **LXD**: Containerized testing via LXD REST API
- Test your connection: `telnet <ip> <port>` (e.g., `telnet 192.168.2.120 6031`)
- **Important**: Exit telnet with `Ctrl+]` then type `quit` before running pytest tests

## Quick Start

```bash
# Install dependencies
python3 -m venv venv && . venv/bin/activate
pip install pytest
pip install git+https://github.com/lgirdk/boardfarm.git@boardfarm3
pip install git+https://github.com/lgirdk/pytest-boardfarm.git@boardfarm3
```

```bash
# Run basic test to verify installation
pytest -p no:pytest_boardfarm3 tests/tests_basic.py -v
```

### Setting up ser2net

ser2net provides serial-to-network proxy access to physical Raspberry Pi devices. This allows remote access to the device's serial console over TCP/IP.

#### Installation

```bash
# Install ser2net on the host connected to your Raspberry Pi
sudo apt-get update
sudo apt-get install ser2net
```

#### Configuration

Edit `/etc/ser2net.conf` to add your serial device:

```bash
# Example configuration for Raspberry Pi serial console
# Format: port:telnet:timeout:device:options
6031:telnet:0:/dev/ttyUSB0:115200 8DATABITS NONE 1STOPBIT banner
```

Key parameters:
- `6031`: TCP port to listen on (choose any available port)
- `telnet`: Connection protocol
- `0`: No timeout (connection stays open)
- `/dev/ttyUSB0`: Serial device (adjust based on your USB-to-serial adapter)
- `115200`: Baud rate (standard for Raspberry Pi console)

#### Starting ser2net

```bash
# Start ser2net service
sudo systemctl start ser2net
sudo systemctl enable ser2net  # Enable on boot

# Or run manually for testing
sudo ser2net -C /etc/ser2net.conf -d
```

#### Verify Connection

```bash
# Test connection to your device
telnet <ser2net_host_ip> 6031

# You should see the Raspberry Pi console
# Exit with Ctrl+] then type 'quit'
```

**Important**: Always exit telnet properly before running pytest tests to avoid connection conflicts.

## RPI CPE Device (Simple Implementation)

The `RpiCpeDevice` class provides a basic device implementation for Raspberry Pi boards. This is the simplest way to get started with boardfarm.

### Features
- Basic command execution via `command(cmd)` method
- Simple serial console access through ser2net
- Minimal configuration required
- Perfect for learning boardfarm fundamentals

### Configuration

Add to `inventory.json`:
```json
{
    "rpi_cpe_1": {
        "devices": [{
            "name": "board",
            "type": "rpi_cpe",
            "connection_type": "ser2net",
            "ip_addr": "192.168.2.120",
            "port": "6031",
            "shell_prompt": "root@RaspberryPi-Gateway"
        }]
    }
}
```

### Running RPI CPE Tests

```bash
# Run all RPI CPE tests
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -v

# Run a specific test
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py::test_cpe_connection -v

# Skip slow tests
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -m "not slow" -v

# Show print statements for debugging
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -v -s
```

### Example Test Code

The RPI CPE tests demonstrate basic device interaction:
```python
def test_cpe_connection(device_manager: DeviceManager):
    """Test connection to CPE device via ser2net"""
    devices = device_manager.get_devices_by_type(RpiCpeDevice)
    cpe = list(devices.values())[0]
    
    output = cpe.command("uname -a")
    assert "Linux" in output
```


## RDK CPE Device (Advanced Template Implementation)

The `RdkCpeDevice` class demonstrates the full boardfarm3 CPE template implementation, following production patterns used in real deployments.

### Architecture

The RDK CPE implementation (`rdk_cpe_device.py`) follows boardfarm3's hardware/software separation pattern with three main classes:

- **RdkRpiHW**: Hardware abstraction layer
  - Serial number retrieval from /proc/cpuinfo
  - MAC address retrieval from network interfaces
  - Power cycle/reboot capabilities
  - Console connection management (ser2net/LXD)

- **RdkSW**: Software abstraction layer
  - Device information collection via dmcli
  - Management server configuration (TR-069/CWMP)
  - Network interface properties (WAN/LAN/Guest)
  - Software version retrieval

- **RdkCpeDevice**: Main device class
  - Inherits from boardfarm3's CPETemplate
  - Combines hardware and software capabilities
  - Provides unified device interface

### Features

- Device information collection (serial, MAC, version)
- Network interface management (WAN/erouter0, LAN/br0)
- System command execution and monitoring
- Hardware control (reboot/power cycle)
- Performance monitoring (via Linux commands)
- Management server configuration (TR-069/CWMP via dmcli)
- Connection support for ser2net and LXD containers

### Configuration

Add to `inventory.json`:
```json
{
    "rdk_cpe_1": {
        "devices": [{
            "name": "board",
            "type": "rdk_cpe",
            "connection_type": "ser2net",
            "ip_addr": "192.168.2.120",
            "port": "6031",
            "shell_prompt": "root@RaspberryPi-Gateway",
            "wan_interface": "erouter0",
            "lan_interface": "br0"
        }]
    }
}
```

### Running RDK CPE Tests

```bash
# Run all RDK CPE tests
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v

# Run with timing information
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v --durations=0

# Run a specific test
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py::test_rdk_cpe_hardware_info -v
```

### Example Test Code

The RDK CPE tests demonstrate advanced device capabilities:
```python
def test_rdk_cpe_hardware_info(device_manager: DeviceManager):
    """Test hardware information retrieval"""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    board = list(devices.values())[0]
    
    # Access hardware properties
    serial = board.hw.serial_number
    mac = board.hw.mac_address
    assert serial and mac
```

## Use Cases - Real-World Testing Scenarios

The `tests_rdk_cpe_use_cases.py` file demonstrates how boardfarm3 is used in production environments for comprehensive device validation.

### What Are Use Cases?

Use cases represent real-world testing scenarios that validate device functionality in practical situations:

- **System Health Monitoring**: CPU, memory, and resource utilization
- **Network Performance**: Throughput testing, latency measurements
- **Service Validation**: Ensuring critical services are running
- **Configuration Management**: Applying and verifying device settings
- **Stress Testing**: Device behavior under load

### How Use Cases Work

1. **Comprehensive Health Checks**: Combine multiple validations into single test
2. **Performance Baselines**: Establish and verify expected performance metrics
3. **Service Dependencies**: Test inter-service relationships and dependencies
4. **Real Traffic Patterns**: Simulate actual network usage patterns

### Running Use Case Tests

```bash
# Run all use case tests
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe_use_cases.py -v

# System monitoring tests
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe_use_cases.py::TestRdkCpeUseCases::test_cpu_usage_monitoring -v
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe_use_cases.py::TestRdkCpeUseCases::test_memory_usage_monitoring -v

# Network performance tests
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe_use_cases.py::TestRdkCpeUseCases::test_wan_connectivity_check -v
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe_use_cases.py::TestRdkCpeUseCases::test_lan_interface_status -v

# Comprehensive validation
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe_use_cases.py::TestRdkCpeUseCases::test_combined_system_health_check -v

# Real boardfarm3 iperf test (requires iperf server)
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe_use_cases.py::TestRdkCpeUseCases::test_iperf_use_case_real -v
```

### Example Use Case Test

```python
def test_combined_system_health_check(self, device_manager: DeviceManager):
    """Comprehensive system health validation"""
    board = self._get_board(device_manager)
    
    # Check CPU usage
    cpu_usage = cpe_use_cases.get_cpu_usage(board)
    assert 0 <= cpu_usage <= 100, f"Invalid CPU usage: {cpu_usage}%"
    
    # Check memory usage  
    mem_usage = cpe_use_cases.get_memory_usage(board)
    assert 0 <= mem_usage <= 100, f"Invalid memory usage: {mem_usage}%"
    
    # Check network connectivity
    wan_status = networking_use_cases.wan_connectivity_check(board)
    assert wan_status["connected"], "WAN connectivity failed"
```

### Production Use Cases

In production boardfarm deployments, use cases extend to:

- **WiFi Client Onboarding**: WPS, manual configuration, band steering
- **IPTV Streaming**: Multicast joins, channel changes, quality metrics
- **Firmware Upgrades**: Download, verification, installation, rollback
- **Security Validation**: Firewall rules, port scans, intrusion detection
- **QoS Testing**: Traffic prioritization, bandwidth management
- **Stability Testing**: Long-duration tests, reboot cycles, stress scenarios

## Test Execution Options

### Required Arguments

- `--board-name`: Board configuration name from inventory.json
- `--env-config`: Path to environment configuration file
- `--inventory-config`: Path to inventory configuration file

### Useful pytest Options

```bash
# Verbose output with print statements
pytest --board-name=rdk_cpe_1 ... -v -s

# Run tests matching a pattern
pytest --board-name=rdk_cpe_1 ... -k "network"

# Run tests with specific markers
pytest --board-name=rdk_cpe_1 ... -m "not slow"

# Show test durations
pytest --board-name=rdk_cpe_1 ... --durations=10

# Stop on first failure
pytest --board-name=rdk_cpe_1 ... -x

# Collect only (don't run)
pytest --board-name=rdk_cpe_1 ... --collect-only
```

## LXD Container Testing

Test the same device classes using LXD containers instead of physical hardware.

### Setup

1. **Generate certificates**:
```bash
openssl req -newkey rsa:2048 -nodes -keyout .config/lxc/client.key \
  -x509 -days 365 -out .config/lxc/client.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=lxd-client"
```

2. **Configure LXD server** (192.168.2.120):
```bash
# Add client certificate
cat .config/lxc/client.crt | ssh user@192.168.2.120 'lxc config trust add -'

# Enable network listening
ssh user@192.168.2.120 'lxc config set core.https_address :8443'

# Create/verify container
ssh user@192.168.2.120 'lxc launch ubuntu:22.04 vcpe'
```

### LXD Configuration

Add to `inventory.json`:
```json
{
  "rdk_cpe_lxd": {
    "devices": [{
      "name": "board",
      "type": "rdk_cpe",
      "connection_type": "lxd",
      "lxd_endpoint": "https://192.168.2.120:8443",
      "cert_file": ".config/lxc/client.crt",
      "key_file": ".config/lxc/client.key",
      "container_name": "vcpe",
      "serial": "1000000007b59242"
    }]
  }
}
```


### Usage

```bash
# Physical hardware
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v

# LXD container (same tests)
pytest --board-name=rdk_cpe_lxd --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v
```


## Known Issues and Solutions

### ps Command Format Compatibility
The RdkCpeDevice class includes overridden `start_traffic_receiver` and `start_traffic_sender` methods that handle different `ps` output formats. This is necessary because:
- Different container environments (LXD, Docker) may have varying `ps` implementations
- The boardfarm3 library assumes a specific ps output format that may not match your environment
- The override dynamically detects the PID column position to ensure compatibility

### HTTP Request Logging
By default, the httpx library logs all HTTP requests at INFO level. The `lxd_connection.py` module sets this to WARNING level to reduce verbosity. Adjust as needed for debugging.
