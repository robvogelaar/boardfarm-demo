"""Pytest configuration for boardfarm integration."""

import sys
import os
from boardfarm3 import hookimpl

# Add current directory to Python path so our modules can be imported
sys.path.insert(0, os.path.dirname(__file__))

# Import our custom devices
from rpi_cpe_device import RpiCpeDevice
from rdk_cpe_device import RdkCpeDevice


@hookimpl
def boardfarm_add_devices():
    """Register custom devices with boardfarm."""
    return {
        "rpi_cpe": RpiCpeDevice,
        "rdk_cpe": RdkCpeDevice
    }


def pytest_configure(config):
    """Configure pytest and register custom devices."""
    from boardfarm3.main import get_plugin_manager
    pm = get_plugin_manager()

    # Register this module as a plugin so the hook is discovered
    pm.register(sys.modules[__name__], name="custom_rpi_devices")
