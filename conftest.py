"""Pytest configuration for boardfarm integration."""

import sys
import os
from boardfarm3 import hookimpl

# Add current directory to Python path so our modules can be imported
sys.path.insert(0, os.path.dirname(__file__))

# Import our custom devices
from rpi_cpe_device import RpiCpeDevice
from rdk_cpe_device import RdkCpeDevice

# Import LXD connection
from lxd_connection import LXDConnection


@hookimpl
def boardfarm_add_devices():
    """Register custom devices with boardfarm."""
    return {
        "rpi_cpe": RpiCpeDevice,
        "rdk_cpe": RdkCpeDevice
    }


def register_lxd_connection():
    """Register LXD connection type with boardfarm."""
    import sys
    from boardfarm3.lib import connection_factory
    from boardfarm3.exceptions import EnvConfigError
    
    # Store the original connection_factory function
    original_factory = connection_factory.connection_factory
    
    # Create a wrapper that adds LXD support
    def patched_connection_factory(connection_type, connection_name, **kwargs):
        if connection_type == "lxd":
            return LXDConnection(
                name=connection_name,
                container_name=kwargs.get("container_name", kwargs.get("hostname", "rdk-container")),
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
    
    # Replace the connection_factory function in the module
    connection_factory.connection_factory = patched_connection_factory
    
    # Also patch any modules that have already imported the function directly
    # This handles cases where modules do "from connection_factory import connection_factory"
    for module_name, module in sys.modules.items():
        if hasattr(module, 'connection_factory'):
            # Check if it's the function we want to replace (not the module)
            if callable(getattr(module, 'connection_factory')) and \
               getattr(module, 'connection_factory').__module__ == 'boardfarm3.lib.connection_factory':
                setattr(module, 'connection_factory', patched_connection_factory)


def pytest_configure(config):
    """Configure pytest and register custom devices."""
    from boardfarm3.main import get_plugin_manager
    pm = get_plugin_manager()

    # Register LXD connection type
    register_lxd_connection()

    # Register this module as a plugin so the hook is discovered
    pm.register(sys.modules[__name__], name="custom_rpi_devices")
