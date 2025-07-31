"""Test cases for RDK CPE device using boardfarm3."""

import pytest
from boardfarm3.lib.device_manager import DeviceManager
from rdk_cpe_device import RdkCpeDevice


@pytest.mark.integration
def test_rdk_cpe_connection(device_manager: DeviceManager):
    """Test RDK CPE device connection."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    assert len(devices) > 0, "No RDK CPE devices found"

    cpe = list(devices.values())[0]
    assert cpe is not None

    # Test basic command execution
    output = cpe.command("echo 'RDK CPE is connected'")
    assert "RDK CPE is connected" in output


@pytest.mark.integration
def test_rdk_cpe_hardware_info(device_manager: DeviceManager):
    """Test RDK CPE hardware information retrieval."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    cpe = list(devices.values())[0]

    # Check hardware properties
    assert cpe.hw is not None
    assert cpe.hw.wan_iface == "erouter0"  # Based on config

    # Test MAC address retrieval
    mac = cpe.hw.mac_address
    assert mac is not None
    assert len(mac) == 17  # MAC address format XX:XX:XX:XX:XX:XX

    # Test serial number
    serial = cpe.hw.serial_number
    assert serial is not None
    assert len(serial) > 0


@pytest.mark.integration
def test_rdk_cpe_software_info(device_manager: DeviceManager):
    """Test RDK CPE software information retrieval."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    cpe = list(devices.values())[0]

    # Check software properties
    assert cpe.sw is not None

    # Test version retrieval
    version = cpe.sw.version
    assert version is not None
    assert len(version) > 0

    # Test interface names
    assert cpe.sw.erouter_iface == "erouter0"
    assert cpe.sw.lan_iface == "br0"

    # Test CPE ID
    cpe_id = cpe.sw.cpe_id
    assert cpe_id is not None
    assert "-" in cpe_id  # Format: OUI-SERIAL


@pytest.mark.integration
def test_rdk_cpe_network_interfaces(device_manager: DeviceManager):
    """Test RDK CPE network interface information."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    cpe = list(devices.values())[0]

    # Check WAN interface
    output = cpe.command(f"ip addr show {cpe.hw.wan_iface}")
    assert cpe.hw.wan_iface in output

    # Check LAN interface
    output = cpe.command(f"ip addr show {cpe.sw.lan_iface}")
    assert cpe.sw.lan_iface in output

    # Get LAN gateway IP
    lan_ip = cpe.sw.lan_gateway_ipv4
    assert lan_ip is not None
    assert str(lan_ip).startswith("192.168.") or str(lan_ip).startswith("10.")


@pytest.mark.integration
def test_rdk_cpe_system_commands(device_manager: DeviceManager):
    """Test RDK CPE system command execution."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    cpe = list(devices.values())[0]

    # Test hostname
    hostname = cpe.command("hostname").strip()
    assert hostname == cpe.hw.config.get("hostname", "RaspberryPi-Gateway")

    # Test kernel info
    kernel = cpe.command("uname -r").strip()
    assert len(kernel) > 0

    # Test uptime
    uptime = cpe.command("uptime")
    assert "load average" in uptime

    # Test process list (BusyBox compatible)
    processes = cpe.command("ps aux | head -n 10")
    assert "PID" in processes or "pid" in processes.lower()


@pytest.mark.integration
@pytest.mark.slow
def test_rdk_cpe_provision_mode(device_manager: DeviceManager):
    """Test RDK CPE provisioning mode."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    cpe = list(devices.values())[0]

    # Check provisioning mode
    mode = cpe.sw.get_provision_mode()
    assert mode in ["ipv4", "ipv6", "dual"]
    assert mode == "ipv4"  # Based on our config


@pytest.mark.integration
def test_rdk_cpe_json_values(device_manager: DeviceManager):
    """Test RDK CPE JSON values retrieval."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    cpe = list(devices.values())[0]

    # Get JSON values (device-specific config/status)
    json_values = cpe.sw.json_values
    assert isinstance(json_values, dict)
    assert len(json_values) > 0

    # Should have at least hostname and kernel
    if "hostname" in json_values:
        assert json_values["hostname"] == cpe.hw.config.get("hostname", "RDK-RaspberryPi")


@pytest.mark.integration
def test_rdk_cpe_mtu_size(device_manager: DeviceManager):
    """Test RDK CPE interface MTU size retrieval."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    cpe = list(devices.values())[0]

    # Check MTU size for WAN interface
    try:
        mtu = cpe.sw.get_interface_mtu_size(cpe.hw.wan_iface)
        assert isinstance(mtu, int)
        assert 1000 <= mtu <= 9000  # Typical MTU range
    except ValueError:
        pytest.skip(f"Interface {cpe.hw.wan_iface} not available")


@pytest.mark.integration
def test_rdk_cpe_is_online(device_manager: DeviceManager):
    """Test if RDK CPE is online."""
    devices = device_manager.get_devices_by_type(RdkCpeDevice)
    cpe = list(devices.values())[0]

    # Check if device is online
    is_online = cpe.sw.is_online()
    assert isinstance(is_online, bool)

    # If online, should be able to ping external host
    if is_online:
        output = cpe.command("ping -c 1 8.8.8.8")
        assert "1 packets transmitted" in output or "1 packets received" in output
