"""Simple Raspberry Pi CPE device for boardfarm."""

from boardfarm3 import hookimpl
from boardfarm3.devices.base_devices import BoardfarmDevice
from boardfarm3.lib.connection_factory import connection_factory


class RpiCpeDevice(BoardfarmDevice):
    """Simple Raspberry Pi CPE device that works with ser2net."""

    def __init__(self, config, cmdline_args):
        """Initialize the RPI CPE device.

        :param config: device configuration
        :param cmdline_args: command line arguments
        """
        super().__init__(config, cmdline_args)
        self._console = None
        self.prompt = config.get("prompt", "root@RaspberryPi-Gateway")

    def connect_to_consoles(self, device_name):
        """Connect to device console using ser2net.

        :param device_name: name of the device
        """
        self._console = connection_factory(
            connection_type=self._config.get("connection_type"),
            connection_name=f"{device_name}.console",
            ip_addr=self._config.get("ip_addr"),
            port=self._config.get("port"),
            shell_prompt=self._config.get("shell_prompt", self.prompt),
            save_console_logs=getattr(self._cmdline_args, 'save_console_logs', None),
        )
        self._console.login_to_server()
        # Clear any initial output
        self._console.sendline("")
        self._console.expect(self._console._shell_prompt, timeout=5)

    def sendline(self, command):
        """Send a command to the device.

        :param command: command to send
        :return: index of matched pattern
        """
        return self._console.sendline(command)

    def expect(self, pattern, timeout=30):
        """Wait for expected pattern.

        :param pattern: pattern to wait for
        :param timeout: timeout in seconds
        :return: index of matched pattern
        """
        return self._console.expect(pattern, timeout=timeout)

    @property
    def before(self):
        """Get output before the last matched pattern."""
        if self._console:
            return self._console.before
        return ""

    def command(self, cmd, timeout=30):
        """Execute a command and return the output.

        :param cmd: command to execute
        :param timeout: timeout in seconds
        :return: command output
        """
        self.sendline(cmd)
        self.expect(self._console._shell_prompt, timeout=timeout)
        return self.before

    @hookimpl
    def boardfarm_device_boot(self):
        """Boot hook to establish connection to the device."""
        self.connect_to_consoles(self.device_name)

    def close(self):
        """Close the device connection."""
        if self._console:
            try:
                self._console.close()
            except:
                pass