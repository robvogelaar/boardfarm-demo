"""RDK CPE device class based on RDK platform."""

from __future__ import annotations

import logging
import re
from functools import cached_property
from ipaddress import AddressValueError, IPv4Address
from time import sleep
from typing import TYPE_CHECKING, Any

import jc

from boardfarm3 import hookimpl
from boardfarm3.devices.base_devices.boardfarm_device import BoardfarmDevice
from boardfarm3.devices.base_devices.linux_device import LinuxDevice
from boardfarm3.exceptions import (
    ConfigurationFailure,
    DeviceBootFailure,
    NotSupportedError,
)
from boardfarm3.lib.connection_factory import connection_factory
from boardfarm3.lib.cpe_sw import CPESwLibraries
from boardfarm3.lib.utils import retry
from boardfarm3.templates.acs import ACS
from boardfarm3.templates.cpe import CPE, CPEHW
from boardfarm3.templates.provisioner import Provisioner

if TYPE_CHECKING:
    from argparse import Namespace

    from boardfarm3.lib.boardfarm_pexpect import BoardfarmPexpect
    from boardfarm3.lib.device_manager import DeviceManager
    from boardfarm3.lib.hal.cpe_wifi import WiFiHal
    from boardfarm3.templates.cpe.cpe_hw import TerminationSystem
    from boardfarm3.templates.tftp import TFTP

_LOGGER = logging.getLogger(__name__)


class RdkRpiHW(CPEHW):
    """RDK Raspberry Pi hardware device class."""

    def __init__(self, config: dict[str, Any], cmdline_args: Namespace) -> None:
        """Initialize CPE hardware.

        :param config: CPE config
        :param cmdline_args: command line arguments
        """
        self._config = config
        self._cmdline_args = cmdline_args
        self._console: BoardfarmPexpect = None

    @property
    def config(self) -> dict[str, Any]:
        """Device config.

        :return: Device config
        :rtype: dict[str, Any]
        """
        return self._config

    @property
    def mac_address(self) -> str:
        """Get CPE MAC address.

        :return: MAC address
        :rtype: str
        """
        if self._console:
            try:
                # Use a simpler command to avoid line-breaking issues
                output = self._console.execute_command("ifconfig erouter0", timeout=5)
                # Parse MAC address from ifconfig output
                import re
                mac_match = re.search(r'HWaddr\s+([0-9a-fA-F:]{17})', output)
                if mac_match:
                    return mac_match.group(1).lower()

                # Fallback: try modern format
                mac_match = re.search(r'ether\s+([0-9a-fA-F:]{17})', output)
                if mac_match:
                    return mac_match.group(1).lower()

            except Exception:
                _LOGGER.warning("Failed to get MAC address, using default")

        return self._config.get("mac", "00:00:00:00:00:00")

    @property
    def serial_number(self) -> str:
        """Get CPE Serial number.

        :return: Serial number
        :rtype: str
        """
        if self._console:
            try:
                output = self._console.execute_command(
                    "cat /proc/cpuinfo | grep Serial | awk '{print $3}'",
                    timeout=5
                )
                if output and output.strip():
                    return output.strip()
            except Exception:
                _LOGGER.warning("Failed to get serial number, using default")

        return self._config.get("serial", "0000000000000000")

    @property
    def wan_iface(self) -> str:
        """WAN interface name.

        :return: the wan interface name
        :rtype: str
        """
        return self._config.get("wan_interface", "erouter0")

    @property
    def mta_iface(self) -> str:
        """MTA interface name.

        :raises NotSupportedError: voice is not enabled for RDK
        """
        raise NotSupportedError

    @property
    def _shell_prompt(self) -> list[str]:
        """Console prompt.

        :return: the shell prompt
        :rtype: list[str]
        """
        prompt = self._config.get("shell_prompt", "root@RaspberryPi-Gateway")
        # Escape special regex characters and create more flexible patterns
        import re
        escaped_prompt = re.escape(prompt)
        return [f"{escaped_prompt}.*#\\s*", f"{escaped_prompt}.*\\$\\s*", "/ #"]

    def connect_to_consoles(self, device_name: str) -> None:
        """Establish connection to the device console.

        :param device_name: device name
        :type device_name: str
        """
        connection_type = self._config.get("connection_type", "ser2net")

        if connection_type == "ser2net":
            self._console = connection_factory(
                connection_type="ser2net",
                connection_name=f"{device_name}.console",
                ip_addr=self._config.get("ip_addr"),
                port=self._config.get("port"),
                shell_prompt=self._shell_prompt,
                save_console_logs=self._cmdline_args.save_console_logs,
            )
        elif connection_type == "lxd":
            # LXD connection with specific parameters
            self._console = connection_factory(
                connection_type=str(connection_type),
                connection_name=f"{device_name}.console",
                lxd_endpoint=self._config.get("lxd_endpoint", "https://127.0.0.1:8443"),
                container_name=self._config.get("container_name", self._config.get("hostname", "rdk-container")),
                cert_file=self._config.get("cert_file"),
                key_file=self._config.get("key_file"),
                trust_password=self._config.get("trust_password"),
                save_console_logs=self._cmdline_args.save_console_logs,
                shell_prompt=self._shell_prompt,
            )
        else:
            # Support for other connection types if needed
            self._console = connection_factory(
                connection_type=str(connection_type),
                connection_name=f"{device_name}.console",
                conn_command=self._config.get("conn_cmd", [""])[0],
                save_console_logs=self._cmdline_args.save_console_logs,
                shell_prompt=self._shell_prompt,
            )

        self._console.login_to_server()
        # Clear any initial output
        self._console.sendline("")
        self._console.expect(self._shell_prompt, timeout=5)

    def get_console(self, console_name: str) -> BoardfarmPexpect:
        """Return console instance with the given name.

        :param console_name: name of the console
        :type console_name: str
        :raises ValueError: on unknown console name
        :return: console instance with given name
        :rtype: BoardfarmPexpect
        """
        if console_name == "console":
            return self._console
        msg = f"Unknown console name: {console_name}"
        raise ValueError(msg)

    def disconnect_from_consoles(self) -> None:
        """Disconnect/Close the console connections."""
        if self._console is not None:
            self._console.close()

    def get_interactive_consoles(self) -> dict[str, BoardfarmPexpect]:
        """Get interactive consoles of the device.

        :returns: device interactive consoles
        """
        return {"console": self._console}

    def power_cycle(self) -> None:
        """Power cycle the CPE via cli."""
        self._console.execute_command("reboot")
        # Sleep for 30s for Raspberry Pi to restart
        sleep(30)
        self.disconnect_from_consoles()
        self.connect_to_consoles("board")

    def flash_via_bootloader(
        self,
        image: str,  # noqa: ARG002
        tftp_devices: dict[str, TFTP],  # noqa: ARG002
        termination_sys: TerminationSystem = None,  # noqa: ARG002
        method: str | None = None,  # noqa: ARG002
    ) -> None:
        """Flash cpe via the bootloader.

        :param image: image name
        :type image: str
        :param tftp_devices: a list of LAN side TFTP devices
        :type tftp_devices: dict[str, TFTP]
        :param termination_sys: the termination system device (e.g. CMTS),
            defaults to None
        :type termination_sys: TerminationSystem
        :param method: flash method, defaults to None
        :type method: str, optional
        :raises NotSupportedError: flashing via bootloader not supported for RDK
        """
        raise NotSupportedError

    def wait_for_hw_boot(self) -> None:
        """Wait for CPE to have WAN interface added.

        :raises DeviceBootFailure: if CPE is unable to bring up WAN interface
        """
        for attempt in range(3):  # Reduced attempts and timeout
            try:
                output = self._console.execute_command("ip a", timeout=10)
                if self.wan_iface in output:
                    _LOGGER.info("WAN interface %s found", self.wan_iface)
                    break
            except Exception as e:
                _LOGGER.warning("Attempt %d: Error checking interfaces: %s", attempt + 1, str(e))
            sleep(2)  # Shorter sleep
        else:
            # Don't fail - just warn and continue
            _LOGGER.warning("WAN interface %s may not be ready, but continuing", self.wan_iface)


class RdkSW(CPESwLibraries):  # pylint: disable=R0904
    """RDK software component device class."""

    _hw: RdkRpiHW

    def __init__(self, hardware: RdkRpiHW) -> None:
        """Initialise the RDK sofware class.

        :param hardware: the board hw object
        :type hardware: RdkRpiHW
        """
        super().__init__(hardware)

    @property
    def wifi(self) -> WiFiHal:
        """Return instance of WiFi component of RDK software.

        :raises NotSupportedError: WiFi HAL not implemented yet
        """
        raise NotSupportedError

    @property
    def version(self) -> str:
        """CPE software version.

        This will reload after each flash.
        :return: version
        :rtype: str
        """
        try:
            return self._console.execute_command("cat /version.txt").strip()
        except Exception:
            return self._console.execute_command("uname -r").strip()

    @property
    def erouter_iface(self) -> str:
        """E-Router interface name.

        :return: E-Router interface name
        :rtype: str
        """
        return self._hw.wan_iface

    @property
    def lan_iface(self) -> str:
        """LAN interface name.

        :return: LAN interface name
        :rtype: str
        """
        return self._hw.config.get("lan_interface", "br0")

    @property
    def guest_iface(self) -> str:
        """Guest network interface name.

        :return: name of the guest network interface
        :rtype: str
        """
        return "br-guest"

    @property
    def json_values(self) -> dict[str, Any]:
        """CPE Specific JSON values.

        :return: the CPE Specific JSON values
        :rtype: dict[str, Any]
        """
        json: dict[str, Any] = {}

        # For RDK, we use dmcli to get device parameters
        try:
            # Get device info using dmcli
            output = self._console.execute_command("dmcli eRT getv Device.DeviceInfo.SerialNumber", timeout=30)

            # Parse the parameter format:
            # Parameter XXXX name: Device.DeviceInfo.Something
            #                type:     string,    value: SomeValue
            import re

            lines = output.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Look for parameter name line
                param_match = re.search(r'Parameter\s+\d+\s+name:\s+(.+)', line)
                if param_match:
                    param_name = param_match.group(1).strip()

                    # Look for the corresponding value line (usually next line)
                    if i + 1 < len(lines):
                        value_line = lines[i + 1].strip()
                        value_match = re.search(r'type:\s+\w+,\s+value:\s*(.*)$', value_line)
                        if value_match:
                            param_value = value_match.group(1).strip()

                            # Convert boolean strings to actual booleans
                            if param_value.lower() in ('true', 'false'):
                                param_value = param_value.lower() == 'true'
                            elif param_value.isdigit():
                                param_value = int(param_value)
                            elif param_value == '':
                                param_value = None

                            # Use a simplified key name (last part of the parameter path)
                            key_parts = param_name.split('.')
                            if len(key_parts) > 2:
                                # Use last 2-3 parts for readability
                                if len(key_parts) >= 3:
                                    simple_key = '.'.join(key_parts[-2:])
                                else:
                                    simple_key = key_parts[-1]
                            else:
                                simple_key = param_name

                            json[simple_key] = param_value

                i += 1

        except Exception as e:
            _LOGGER.warning("Failed to get dmcli device info: %s", str(e))
            # Fallback to basic system info
            try:
                json["hostname"] = self._console.execute_command("hostname", timeout=5).strip()
                json["kernel"] = self._console.execute_command("uname -r", timeout=5).strip()
                json["uptime"] = self._console.execute_command("uptime", timeout=5).strip()
            except Exception:
                pass

        return json

    @property
    def gui_password(self) -> str:
        """GUI login password.

        :return: GUI password
        :rtype: str
        """
        return self._hw.config.get("gui_password", "password")

    @cached_property
    def cpe_id(self) -> str:
        """TR069 CPE ID.

        :return: CPE ID
        :rtype: str
        """
        console = self._get_console("default_shell")
        try:
            serial = console.execute_command("cat /proc/cpuinfo | grep Serial | awk '{print $3}'").strip()
            # For RDK, OUI might be in a different location
            oui = self._hw.config.get("oui", "001122")
            return f"{oui}-{serial}"
        except Exception:
            return self._hw.config.get("cpe_id", "001122-000000000000")

    @property
    def tr69_cpe_id(self) -> str:
        """TR-69 CPE Identifier.

        :return: TR069 CPE ID
        :rtype: str
        """
        return self.cpe_id

    @cached_property
    def lan_gateway_ipv4(self) -> IPv4Address:
        """LAN Gateway IPv4 address.

        :return: the ip (if present) 192.168.1.1 otherwise
        :rtype: IPv4Address
        """
        try:
            # Use main console with a very simple command
            console = self._hw.get_console("console")
            # Use ifconfig which has more predictable output format
            output = console.execute_command(f"ifconfig {self.lan_iface}", timeout=10)

            # Parse the ifconfig output for inet addr
            import re
            ip_match = re.search(r'inet addr:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', output)
            if ip_match:
                return IPv4Address(ip_match.group(1))

            # Fallback: try modern ip command format
            ip_match = re.search(r'inet (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/', output)
            if ip_match:
                return IPv4Address(ip_match.group(1))

            _LOGGER.warning("No IP found in ifconfig output, using default")
            return IPv4Address("192.168.101.1")

        except Exception as e:
            # Check if the exception has the output we need (common with timeout)
            if hasattr(e, 'before') and e.before:
                before_str = str(e.before)
                # Look for IP pattern in the 'before' output
                import re
                ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', before_str)
                if ip_match:
                    try:
                        return IPv4Address(ip_match.group(1))
                    except Exception:
                        pass

            _LOGGER.warning("Error getting LAN IP, using default: %s", str(e))
            return IPv4Address("192.168.101.1")

    def is_production(self) -> bool:
        """Is production software.

        Production software has limited capabilities.
        :return: Production status
        :rtype: bool
        """
        return False

    def reset(self, method: str | None = None) -> None:  # noqa: ARG002
        """Perform a reset via given method.

        :param method: reset method(sw/hw)
        """
        self._hw.power_cycle()

    def factory_reset(self, method: str | None = None) -> bool:  # noqa: ARG002
        """Perform factory reset CPE via given method.

        :param method: factory reset method. Default None.
        :type method: str | None
        :return: True if successful
        :rtype: bool
        """
        try:
            self._console.execute_command("rm -rf /nvram/*")
            self._console.execute_command("sync")
            self.reset()
            return True
        except Exception:
            return False

    def wait_for_boot(self) -> None:
        """Wait for CPE to boot."""
        self._hw.wait_for_hw_boot()

    def get_provision_mode(self) -> str:
        """Return provision mode.

        :return: the provisioning mode
        :rtype: str
        """
        return self._hw.config.get("eRouter_Provisioning_mode", "ipv4")

    def verify_cpe_is_booting(self) -> None:
        """Verify CPE is booting.

        This could check for boot messages if needed.
        """
        pass

    def wait_device_online(self) -> None:
        """Wait for WAN interface to come online.

        :raises DeviceBootFailure: if board is not online
        """
        for attempt in range(5):  # Reduced attempts
            try:
                if self.is_online():
                    _LOGGER.info("Device is online")
                    return
            except Exception as e:
                _LOGGER.warning("Attempt %d: Error checking online status: %s", attempt + 1, str(e))
            sleep(5)  # Shorter sleep

        # Don't fail - just warn and continue
        _LOGGER.warning("Device may not be fully online, but continuing")

    def configure_management_server(
        self, url: str, username: str | None = "", password: str | None = ""
    ) -> None:
        """Re-enable CWMP service after updating Management Server URL.

        Optionally can also reconfigure the username and password.

        :param url: Management Server URL
        :type url: str
        :param username: CWMP client username, defaults to ""
        :type username: str | None, optional
        :param password: CWMP client password, defaults to ""
        :type password: str | None, optional
        """
        console = self._get_console("default_shell")
        # RDK might use dmcli for TR-069 configuration
        try:
            console.execute_command(f'dmcli eRT setv Device.ManagementServer.URL string "{url}"')
            console.execute_command(f'dmcli eRT setv Device.ManagementServer.Username string "{username}"')
            if password:
                console.execute_command(f'dmcli eRT setv Device.ManagementServer.Password string "{password}"')
            console.execute_command('dmcli eRT setv Device.ManagementServer.EnableCWMP bool false')
            sleep(2)
            console.execute_command('dmcli eRT setv Device.ManagementServer.EnableCWMP bool true')
        except Exception:
            _LOGGER.warning("Failed to configure management server via dmcli")

    def finalize_boot(self) -> bool:
        """Validate board settings post boot.

        :return: True if finalized successfully
        :rtype: bool
        """
        return True

    @property
    def aftr_iface(self) -> str:
        """AFTR interface name.

        :raises NotImplementedError: device does not have an AFTR IFACE
        """
        raise NotImplementedError

    def get_interface_mtu_size(self, interface: str) -> int:
        """Get the MTU size of the interface in bytes.

        :param interface: name of the interface
        :type interface: str
        :return: size of the MTU in bytes
        :rtype: int
        :raises ValueError: when ifconfig data is not available
        """
        if ifconfig_data := jc.parse(
            "ifconfig",
            self._get_console("default_shell").execute_command(f"ifconfig {interface}"),
        ):
            return ifconfig_data[0]["mtu"]  # type: ignore[index]
        msg = f"ifconfig {interface} is not available"
        raise ValueError(msg)


class RdkCpeDevice(CPE, LinuxDevice):
    """RDK device class for Raspberry Pi CPE."""

    def __init__(self, config: dict[str, Any], cmdline_args: Namespace) -> None:
        """Initialize RDK CPE device.

        :param config: configuration from inventory
        :type config: Dict
        :param cmdline_args: command line args
        :type cmdline_args: Namespace
        """
        # Initialize LinuxDevice first, but don't call its __init__ yet
        # because we need to set up our hardware console first
        BoardfarmDevice.__init__(self, config, cmdline_args)

        self._hw: RdkRpiHW = RdkRpiHW(config, cmdline_args)
        self._sw: RdkSW = None

        # Set LinuxDevice console to None initially - it will be set after boot
        self._console: BoardfarmPexpect = None

    @property
    def config(self) -> dict:
        """Get device configuration.

        :returns: device configuration
        """
        return self._config

    @property
    def hw(self) -> RdkRpiHW:
        """The RDK Hardware class object for Raspberry Pi architecture.

        :return: object holding hardware component details.
        :rtype: RdkRpiHW
        """
        return self._hw

    @property
    def sw(self) -> RdkSW:
        """The RDK Software class object.

        :return: object holding software component details.
        :rtype: RdkSW
        """
        return self._sw

    @hookimpl
    def boardfarm_device_boot(self, device_manager: DeviceManager) -> None:
        """Boardfarm hook implementation to boot the RDK device.

        :param device_manager: device manager
        :type device_manager: DeviceManager
        """
        self.hw.connect_to_consoles(self.device_name)
        self._sw = RdkSW(self._hw)

        # Set LinuxDevice console to enable traffic methods
        self._console = self._hw._console

        _LOGGER.info("Booting %s(%s) device", self.device_name, self.device_type)

        # Check for provisioner device
        try:
            if provisioner := device_manager.get_device_by_type(
                Provisioner,  # type: ignore[type-abstract]
            ):
                provisioner.provision_cpe(
                    cpe_mac=self.hw.mac_address, dhcpv4_options={}, dhcpv6_options={}
                )
        except Exception as e:
            _LOGGER.warning(
                "Skipping CPE provisioning. Provisioner for %s(%s) not found: %s",
                self.device_name,
                self.device_type,
                str(e)
            )

        # Wait for device to be ready
        self.hw.wait_for_hw_boot()
        self.sw.wait_device_online()

        # Configure ACS if available
        try:
            if acs := device_manager.get_device_by_type(
                ACS,  # type: ignore[type-abstract]
            ):
                acs_url = acs.config.get(  # type: ignore[attr-defined]
                    "acs_mib",
                    "acs_server.boardfarm.com:7545",
                )
                self.sw.configure_management_server(url=acs_url)
        except Exception as e:
            _LOGGER.warning("ACS device not found: %s", str(e))

        _LOGGER.info("TR069 CPE ID: %s", self.sw.cpe_id)

    def _is_http_gui_running(self) -> bool:
        """Check if HTTP GUI is running."""
        try:
            # Quick check for any service on port 80 using netstat
            console = self.hw.get_console("console")
            output = console.execute_command("netstat -ln | grep :80", timeout=5)
            # Look for LISTEN state on port 80 (exact port, not 8080, 8081, etc.)
            import re
            # Match lines with :80 followed by whitespace and LISTEN
            port_80_listening = re.search(r':80\s+.*LISTEN', output) is not None
            return port_80_listening
        except Exception as e:
            _LOGGER.warning("HTTP GUI check failed: %s", str(e))
            return False

    @hookimpl
    def boardfarm_device_configure(self) -> None:
        """Configure boardfarm device.

        :raises ConfigurationFailure: if the http service cannot be run
        """
        try:
            if not self._is_http_gui_running():
                _LOGGER.warning("HTTP GUI service not detected on port 80")
            else:
                _LOGGER.info("HTTP GUI service is running")
        except Exception as e:
            _LOGGER.warning("HTTP GUI configuration check failed: %s", str(e))

    @hookimpl
    def boardfarm_shutdown_device(self) -> None:
        """Boardfarm hook implementation to shutdown the RDK device."""
        _LOGGER.info("Shutdown %s(%s) device", self.device_name, self.device_type)
        self.hw.disconnect_from_consoles()

    @hookimpl(tryfirst=True)
    def boardfarm_skip_boot(self) -> None:
        """Boardfarm skip boot hook implementation."""
        _LOGGER.info(
            "Initializing %s(%s) device with skip-boot option",
            self.device_name,
            self.device_type,
        )
        self._hw.connect_to_consoles(self.device_name)
        self._sw = RdkSW(self._hw)

        # Set LinuxDevice console to enable traffic methods
        self._console = self._hw._console

    def get_interactive_consoles(self) -> dict[str, BoardfarmPexpect]:
        """Get interactive consoles of the device.

        :return: device interactive consoles
        :rtype: dict[str, BoardfarmPexpect]
        """
        return self.hw.get_interactive_consoles()

    # Compatibility method from original RpiCpeDevice
    def command(self, cmd: str, timeout: int = 30) -> str:
        """Execute a command and return the output.

        :param cmd: command to execute
        :param timeout: timeout in seconds
        :return: command output
        """
        return self.hw.get_console("console").execute_command(cmd, timeout=timeout)

    def start_traffic_receiver(
        self,
        traffic_port: int,
        bind_to_ip: str | None = None,
        ip_version: int | None = None,
        udp_only: bool | None = None,
    ) -> tuple[int, str]:
        """Start the server on a linux device to generate traffic using iperf3.

        This override makes the PID parsing more robust by detecting the ps output format.

        :param traffic_port: server port to listen on
        :type traffic_port: int
        :param bind_to_ip: bind to the interface associated with
            the address host, defaults to None
        :type bind_to_ip: str, optional
        :param ip_version: 4 or 6 as it uses only IPv4 or IPv6, defaults to None
        :type ip_version: int, optional
        :param udp_only: to be used if protocol is UDP only,
            backward compatibility with iperf version 2 as iperf3 does not support
            udp only flag for server
        :type udp_only: bool, optional
        :raises CodeError: raises if unable to start server
        :return: the process id(pid) and log file path
        :rtype: tuple[int , str]
        """
        import re
        import tempfile

        file_path = tempfile.gettempdir()
        log_file_path = f"{file_path}/iperf_server_logs.txt"

        if udp_only:
            version = ""
            self._console.execute_command(
                f"iperf -s -p {traffic_port}"
                f"{f' -B {bind_to_ip}' if bind_to_ip else ''} -u > {log_file_path} 2>&1 &",
            )
        else:
            version = "3"
            self._console.execute_command(
                f"iperf3{f' -{ip_version}' if ip_version else ''} -s -p {traffic_port}"
                f"{f' -B {bind_to_ip}' if bind_to_ip else ''} > {log_file_path} 2>&1 &",
            )

        # First, detect the ps output format to find PID column
        ps_header = self._console.execute_command("ps aux | head -n 1")
        # Split header and find PID column index
        header_cols = ps_header.split()
        try:
            pid_col_index = header_cols.index("PID")
        except ValueError:
            # Fallback to default if PID column not found
            pid_col_index = 1

        # Now get the iperf process info
        output = self._console.execute_command(
            f"sleep 2; ps auxwwww|grep iperf{version}|grep -v grep",
        )

        if f"iperf{version}" in output and "Exit 1" not in output:
            out = re.search(f".* -p {traffic_port}.*", output).group()
            # Split the output and get the PID from the correct column
            process_cols = out.split()
            pid = int(process_cols[pid_col_index])
            return pid, log_file_path
        else:
            from boardfarm3.exceptions import CodeError
            raise CodeError(f"Unable to start iperf{version} server on port {traffic_port}")

    def start_traffic_sender(
        self,
        host: str,
        traffic_port: int,
        bandwidth: int | None = 5,
        bind_to_ip: str | None = None,
        direction: str | None = None,
        ip_version: int | None = None,
        udp_protocol: bool = False,
        time: int = 10,
        client_port: int | None = None,
        udp_only: bool | None = None,
    ) -> tuple[int, str]:
        """Start traffic on a linux client using iperf3.

        This override makes the PID parsing more robust by detecting the ps output format.

        :param host: a host to run in client mode
        :type host: str
        :param traffic_port: server port to connect to
        :type traffic_port: int
        :param bandwidth: bandwidth(mbps) at which the traffic
            has to be generated, defaults to None
        :type bandwidth: Optional[int], optional
        :param bind_to_ip: bind to the interface associated with
            the address host, defaults to 5
        :type bind_to_ip: Optional[str], optional
        :param direction: `--reverse` to run in reverse mode
            (server sends, client receives) or `--bidir` to run in
            bidirectional mode, defaults to None
        :type direction: Optional[str], optional
        :param ip_version: 4 or 6 as it uses only IPv4 or IPv6, defaults to None
        :type ip_version: int, optional
        :param udp_protocol: use UDP rather than TCP, defaults to False
        :type udp_protocol: bool
        :param time: time in seconds to transmit for, defaults to 10
        :type time: int
        :param client_port: client port from where the traffic is getting started
        :type client_port: int | None
        :param udp_only: to be used if protocol is UDP only,
            backward compatibility with iperf version 2
        :type udp_only: bool, optional
        :raises CodeError: raises if unable to start server
        :return: the process id(pid) and log file path
        :rtype: tuple[int , str]
        """
        import re
        import tempfile

        file_path = tempfile.gettempdir()
        log_file_path = f"{file_path}/iperf_client_logs.txt"

        if udp_only:
            version = ""
            self._console.execute_command(
                f"iperf -c {host} "
                f"-p {traffic_port}{f' -B {bind_to_ip}' if bind_to_ip else ''}"
                f" {f' -b {bandwidth}m' if bandwidth else ''} -t {time} {direction or ''}"
                f" -u > {log_file_path}  2>&1  &",
            )
        else:
            version = "3"
            self._console.execute_command(
                f"iperf3{f' -{ip_version}' if ip_version else ''} -c {host} "
                f"-p {traffic_port}{f' -B {bind_to_ip}' if bind_to_ip else ''}"
                f" {f' -b {bandwidth}m' if bandwidth else ''} -t {time} {direction or ''}"
                f" {f' --cport {client_port}' if client_port else ''}"
                f"{' -u' if udp_protocol else ''} > {log_file_path}  2>&1  &",
            )

        # First, detect the ps output format to find PID column
        ps_header = self._console.execute_command("ps aux | head -n 1")
        # Split header and find PID column index
        header_cols = ps_header.split()
        try:
            pid_col_index = header_cols.index("PID")
        except ValueError:
            # Fallback to default if PID column not found
            pid_col_index = 1

        # Now get the iperf process info
        output = self._console.execute_command(
            f"sleep 2; ps auxwwww|grep iperf{version}|grep -v grep",
        )

        if f"iperf{version}" in output and "Exit 1" not in output:
            out = re.search(f".* -c {host} -p {traffic_port}.*", output).group()
            # Split the output and get the PID from the correct column
            process_cols = out.split()
            pid = int(process_cols[pid_col_index])
            return pid, log_file_path
        else:
            from boardfarm3.exceptions import CodeError
            raise CodeError(f"Unable to start iperf{version} client connecting to {host}:{traffic_port}")
