import pytest
from boardfarm3.lib.device_manager import DeviceManager
from rpi_cpe_device import RpiCpeDevice


def test_cpe_connection(device_manager: DeviceManager):
    """Test connection to CPE device via ser2net and run basic commands."""
    # Get the CPE device by type (boardfarm uses device class to identify devices)
    devices = device_manager.get_devices_by_type(RpiCpeDevice)
    assert len(devices) > 0, "No rpi_cpe devices found"

    cpe = list(devices.values())[0]  # Get the first (and only) rpi_cpe device
    print(f"Got device: {cpe}")

    # Test basic connection by running uname command
    output = cpe.command("uname -a")

    # Verify the output contains expected information
    assert "Linux" in output
    assert "RaspberryPi-Gateway" in output
    print(f"System info: {[line.strip() for line in output.split() if 'Linux' in line and 'RaspberryPi-Gateway' in line]}")


def test_cpe_system_info(device_manager: DeviceManager):
    """Test retrieving system information from CPE device."""
    cpe = list(device_manager.get_devices_by_type(RpiCpeDevice).values())[0]

    # Check hostname
    output = cpe.command("hostname")
    assert "RaspberryPi-Gateway" in output

    # Check uptime
    output = cpe.command("uptime")
    assert "load average" in output


def test_cpe_network_interface(device_manager: DeviceManager):
    """Test network interface information on CPE device."""
    cpe = list(device_manager.get_devices_by_type(RpiCpeDevice).values())[0]

    # Check network interfaces
    output = cpe.command("ip addr show")

    # Should have at least loopback interface
    assert "lo:" in output or "127.0.0.1" in output


@pytest.mark.slow
def test_cpe_long_running_command(device_manager: DeviceManager):
    """Test a longer running command on CPE device."""
    cpe = list(device_manager.get_devices_by_type(RpiCpeDevice).values())[0]

    # Run a command that takes some time
    output = cpe.command("sleep 2 && echo 'sleep completed'", timeout=10)
    assert "sleep completed" in output


def test_cpe_file_operations(device_manager: DeviceManager):
    """Test basic file operations on CPE device."""
    cpe = list(device_manager.get_devices_by_type(RpiCpeDevice).values())[0]

    # Create a test file
    cpe.command("echo 'test content' > /tmp/test_file")

    # Read the file back
    output = cpe.command("cat /tmp/test_file")
    assert "test content" in output

    # Clean up
    cpe.command("rm /tmp/test_file")
