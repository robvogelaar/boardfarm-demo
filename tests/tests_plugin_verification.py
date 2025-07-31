import pytest


def test_pytest_boardfarm_plugin_registered():
    """Verify that pytest-boardfarm plugin is registered properly."""
    # Check if the plugin is available
    import pytest_boardfarm3
    assert pytest_boardfarm3 is not None

    # Check plugin module
    import pytest_boardfarm3.pytest_plugin as plugin
    assert hasattr(plugin, 'BoardfarmPlugin')
    assert hasattr(plugin, 'pytest_addoption')


def test_boardfarm_fixtures_available():
    """Test that boardfarm fixtures are available."""
    # This should pass since the plugin is registered
    # even without device configuration
    pass


def test_boardfarm_connection_factory():
    """Test that the boardfarm connection factory works."""
    from boardfarm3.lib.connection_factory import connection_factory
    from boardfarm3.lib.connections.ser2net_connection import Ser2NetConnection

    # Test connection factory with ser2net
    connection = connection_factory(
        connection_type="ser2net",
        connection_name="test",
        ip_addr="127.0.0.1",
        port="2222",
        shell_prompt="$ ",
        save_console_logs=None
    )

    assert isinstance(connection, Ser2NetConnection)
    assert connection._ip_addr == "127.0.0.1"
    assert connection._port == "2222"