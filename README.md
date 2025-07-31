# Boardfarm CPE Demo

A getting started guide for pytest-boardfarm integration, demonstrating foundational device implementation concepts with Raspberry Pi based RDK CPE devices.

## Introduction

[Boardfarm](https://github.com/lgirdk/boardfarm) is a pytest plugin for automated testing of network devices. **Production environments** include:

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
- **ser2net connection method**: Requires a ser2net setup to your Raspberry Pi for device communication
  - Test your connection before running tests: `telnet <ip> <port>` (e.g., `telnet 192.168.2.120 6031`)
  - **Important**: Exit telnet with `Ctrl+]` then type `quit` before running pytest tests (only one connection allowed)

## Quick Start

```bash
# Install dependencies
python3 -m venv venv && . venv/bin/activate
pip install pytest
pip install git+https://github.com/lgirdk/boardfarm.git@boardfarm3
pip install git+https://github.com/lgirdk/pytest-boardfarm.git@boardfarm3
```


```bash
# Update `inventory.json` with your device details:
{
    "rpi_cpe_1": {"devices": [{"name": "board", "type": "rpi_cpe", "ip_addr": "192.168.2.120", "port": "6031"}]},
    "rdk_cpe_1": {"devices": [{"name": "board", "type": "rdk_cpe", "ip_addr": "192.168.2.120", "port": "6031", "wan_interface": "erouter0"}]}
}
```

```bash
# Run tests
pytest -p no:pytest_boardfarm3 tests/tests_basic.py -v  # Basic tests
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -v  # Simple RPI
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v  # Advanced RDK
./run_all_tests.sh  # All tests
```


## Usage

### Running Tests

The project includes several test files in the `tests/` directory, each serving different purposes:

#### 1. Basic Tests (tests_basic.py)
Simple pytest examples without boardfarm integration:
```bash
# Run basic tests without boardfarm plugin
pytest -p no:pytest_boardfarm3 tests/tests_basic.py -v

# Example output: Tests basic pytest functionality like fixtures, parametrization, and markers
```

#### 2. Simple RPI CPE Tests (tests_rpi_cpe.py)
Tests using boardfarm's device manager to interact with simple RPI CPE devices:
```bash
# Run all RPI CPE tests (requires device connection)
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -v

# Run a specific test
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py::test_cpe_connection -v

# Skip slow tests
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -m "not slow" -v
```

#### 3. Advanced RDK CPE Tests (tests_rdk_cpe.py)
Comprehensive tests for the advanced RDK CPE implementation:
```bash
# Run all RDK CPE tests (requires device connection)
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v

# Run with timing information to see performance
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v --durations=0

# Run a specific test
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py::test_rdk_cpe_hardware_info -v
```

#### 4. Plugin Verification Tests (tests_plugin_verification.py)
Tests to verify boardfarm plugin registration:
```bash
# Run plugin verification tests
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_plugin_verification.py -v
```

### Common Test Options

```bash
# Run with verbose output and show print statements
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -v -s

# Run only integration tests
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json -m integration -v

# Run all tests except slow ones
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json -m "not slow" -v

# Collect tests without running (useful for debugging)
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json --collect-only
```

### Running All Tests

You can run all tests using the provided script:

```bash
./run_all_tests.sh
```

Or run tests individually:

```bash
# Run basic tests without boardfarm
pytest -p no:pytest_boardfarm3 tests/tests_basic.py -v

# Run simple RPI CPE tests
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -v

# Run advanced RDK CPE tests  
pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v

# Run plugin verification tests
pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_plugin_verification.py -v
```

### Required Arguments for Boardfarm Tests

- `--board-name`: Name of the board configuration in inventory.json
- `--env-config`: Path to environment configuration file (env_config.json)
- `--inventory-config`: Path to inventory configuration file (inventory.json)

### Important Notes

1. **Test Isolation**: Basic tests (`tests_basic.py`) must be run without the boardfarm plugin as they are pure pytest examples without boardfarm integration.

2. **Test Collection**: The boardfarm plugin may interfere with normal pytest test collection when enabled, which is why running `pytest tests/` doesn't work as expected.

## Device Classes

**RpiCpeDevice** (`rpi_cpe_device.py`): Basic command execution via `command(cmd)` method

**RdkCpeDevice** (`rdk_cpe_device.py`): Full boardfarm3 template implementation:
- Hardware/Software separation (RdkRpiHW and RdkSW classes)
- Data model access
- Advanced networking features
