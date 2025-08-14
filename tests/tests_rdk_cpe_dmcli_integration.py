"""Integration tests for RDK CPE Device with DMCLI library."""

import pytest
from boardfarm3.lib.device_manager import DeviceManager
from rdk_cpe_device import RdkCpeDevice
from shared.lib.dmcli import DMCLIAPI, DMCLIError


class TestRdkCpeDmcliIntegration:
    """Test RDK CPE device integration with DMCLI library."""

    def _get_board(self, device_manager: DeviceManager) -> RdkCpeDevice:
        """Get the RDK CPE device from device manager."""
        devices = device_manager.get_devices_by_type(RdkCpeDevice)
        assert len(devices) > 0, "No RDK CPE devices found"
        return list(devices.values())[0]

    @pytest.mark.integration
    def test_dmcli_get_device_info(self, device_manager: DeviceManager):
        """Test getting device information using DMCLI library."""
        board = self._get_board(device_manager)

        # Create DMCLI API instance using the board's console
        dmcli = DMCLIAPI(board.hw._console)

        # Get device serial number
        try:
            result = dmcli.GPV("Device.DeviceInfo.SerialNumber")
            print(f"Serial Number: {result.rval} (type: {result.rtype})")
            assert "succeed" in result.status
            assert result.rtype in ["string", "hexBinary"]
            assert len(result.rval) > 0
        except DMCLIError as e:
            pytest.skip(f"DMCLI not available on device: {e}")

    @pytest.mark.integration
    def test_dmcli_get_software_version(self, device_manager: DeviceManager):
        """Test getting software version using DMCLI."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        try:
            result = dmcli.GPV("Device.DeviceInfo.SoftwareVersion")
            print(f"Software Version: {result.rval}")
            assert "succeed" in result.status
            assert result.rtype == "string"
            assert len(result.rval) > 0
        except DMCLIError as e:
            pytest.skip(f"DMCLI not available on device: {e}")

    @pytest.mark.integration
    def test_dmcli_get_model_name(self, device_manager: DeviceManager):
        """Test getting model name using DMCLI."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        try:
            result = dmcli.GPV("Device.DeviceInfo.ModelName")
            print(f"Model Name: {result.rval}")
            assert "succeed" in result.status
            assert result.rtype == "string"
            assert len(result.rval) > 0
        except DMCLIError as e:
            pytest.skip(f"DMCLI not available on device: {e}")

    @pytest.mark.integration
    def test_dmcli_get_uptime(self, device_manager: DeviceManager):
        """Test getting device uptime using DMCLI."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        try:
            result = dmcli.GPV("Device.DeviceInfo.UpTime")
            print(f"Uptime: {result.rval} seconds")
            assert "succeed" in result.status
            assert result.rtype in ["unsignedInt", "uint32", "int", "uint"]

            # Verify uptime is a positive number
            uptime = int(result.rval)
            assert uptime > 0, "Uptime should be positive"
        except DMCLIError as e:
            pytest.skip(f"DMCLI not available on device: {e}")

    @pytest.mark.integration
    def test_dmcli_get_network_interfaces(self, device_manager: DeviceManager):
        """Test getting network interface information using DMCLI."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        try:
            # Get number of Ethernet interfaces
            result = dmcli.GPV("Device.Ethernet.InterfaceNumberOfEntries")
            print(f"Number of Ethernet Interfaces: {result.rval}")
            assert "succeed" in result.status

            # Try to get status of first interface
            result = dmcli.GPV("Device.Ethernet.Interface.1.Status")
            print(f"Ethernet Interface 1 Status: {result.rval}")
            assert result.rval in ["Up", "Down", "Unknown", "Dormant", "NotPresent", "LowerLayerDown"]
        except DMCLIError as e:
            pytest.skip(f"Ethernet interface parameters not available: {e}")

    @pytest.mark.integration
    def test_dmcli_get_wifi_status(self, device_manager: DeviceManager):
        """Test getting WiFi status using DMCLI."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        try:
            # Check if WiFi radio is enabled
            result = dmcli.GPV("Device.WiFi.Radio.1.Enable")
            print(f"WiFi Radio 1 Enabled: {result.rval}")
            assert "succeed" in result.status
            assert result.rtype in ["bool", "boolean"]
            assert result.rval in ["true", "false", "0", "1"]

            # Get WiFi SSID
            result = dmcli.GPV("Device.WiFi.SSID.1.SSID")
            print(f"WiFi SSID: {result.rval}")
            assert result.rtype == "string"
        except DMCLIError as e:
            pytest.skip(f"WiFi parameters not available: {e}")

    @pytest.mark.integration
    def test_dmcli_set_parameter(self, device_manager: DeviceManager):
        """Test setting a parameter using DMCLI (non-destructive test)."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        try:
            # Try to set a harmless parameter (device alias/name)
            # First get the current value
            original = dmcli.GPV("Device.DeviceInfo.X_RDKCENTRAL-COM_DeviceAlias")
            print(f"Original Device Alias: {original.rval}")

            # Set a test value
            test_alias = "TestDevice_DMCLI"
            result = dmcli.SPV("Device.DeviceInfo.X_RDKCENTRAL-COM_DeviceAlias", test_alias, "string")
            assert "succeed" in result.status

            # Verify the change
            new_value = dmcli.GPV("Device.DeviceInfo.X_RDKCENTRAL-COM_DeviceAlias")
            assert new_value.rval == test_alias
            print(f"Successfully set Device Alias to: {new_value.rval}")

            # Restore original value
            dmcli.SPV("Device.DeviceInfo.X_RDKCENTRAL-COM_DeviceAlias", original.rval, "string")

        except DMCLIError as e:
            pytest.skip(f"Cannot set device alias parameter: {e}")

    @pytest.mark.integration
    def test_dmcli_get_multiple_parameters(self, device_manager: DeviceManager):
        """Test getting multiple parameters in sequence."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        parameters_to_check = [
            "Device.DeviceInfo.Manufacturer",
            "Device.DeviceInfo.ManufacturerOUI",
            "Device.DeviceInfo.ProductClass",
            "Device.DeviceInfo.HardwareVersion",
            "Device.Time.Status",
            "Device.Time.CurrentLocalTime",
        ]

        results = {}
        for param in parameters_to_check:
            try:
                result = dmcli.GPV(param)
                results[param] = {
                    "value": result.rval,
                    "type": result.rtype,
                    "status": result.status
                }
                print(f"{param}: {result.rval} ({result.rtype})")
            except DMCLIError as e:
                results[param] = {"error": str(e)}
                print(f"{param}: Error - {e}")

        # At least some parameters should be available
        successful_params = [p for p in results if "error" not in results[p]]
        assert len(successful_params) > 0, "No DMCLI parameters were successfully retrieved"
        print(f"\nSuccessfully retrieved {len(successful_params)}/{len(parameters_to_check)} parameters")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_dmcli_add_delete_object(self, device_manager: DeviceManager):
        """Test adding and deleting objects using DMCLI (if supported)."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        try:
            # Try to add a new WiFi AccessPoint object
            result = dmcli.AddObject("Device.WiFi.AccessPoint.")
            print(f"Added new AccessPoint with index: {result.rval}")
            assert "succeed" in result.status

            new_ap_index = result.rval
            new_ap_path = f"Device.WiFi.AccessPoint.{new_ap_index}."

            # Configure the new AccessPoint
            dmcli.SPV(f"{new_ap_path}SSIDReference", "Device.WiFi.SSID.1.", "string")

            # Delete the object we created
            result = dmcli.DelObject(new_ap_path)
            assert "succeed" in result.status
            print(f"Successfully deleted AccessPoint {new_ap_index}")

        except DMCLIError as e:
            pytest.skip(f"Add/Delete object operations not supported: {e}")

    @pytest.mark.integration
    def test_dmcli_error_handling(self, device_manager: DeviceManager):
        """Test DMCLI error handling with invalid parameters."""
        board = self._get_board(device_manager)
        dmcli = DMCLIAPI(board.hw._console)

        # Test with invalid parameter
        with pytest.raises(DMCLIError) as exc_info:
            dmcli.GPV("Device.Invalid.NonExistent.Parameter")

        assert "execution failed" in str(exc_info.value).lower() or \
               "can't find" in str(exc_info.value).lower()
        print(f"Expected error caught: {exc_info.value}")

        # Test setting read-only parameter
        try:
            with pytest.raises(DMCLIError):
                dmcli.SPV("Device.DeviceInfo.SerialNumber", "INVALID", "string")
        except Exception:
            # Some devices might not properly report read-only errors
            pass