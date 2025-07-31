#!/bin/bash
# Run all tests for both RPI and RDK CPE device implementations

set -e  # Exit on any error

echo "=========================================="
echo "Running Boardfarm CPE Demo Test Suite"
echo "=========================================="
echo

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Virtual environment not activated. Please run:"
    echo "   source venv/bin/activate"
    exit 1
fi

echo "🧪 Running basic tests (no device required)..."
echo "----------------------------------------------"
pytest -p no:pytest_boardfarm3 tests/tests_basic.py -v
echo

echo "🔧 Running simple RPI CPE tests..."
echo "-----------------------------------"
if pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rpi_cpe.py -v --tb=short; then
    echo "✅ Simple RPI CPE tests passed"
else
    echo "❌ Simple RPI CPE tests failed or device unavailable"
fi
echo

echo "🚀 Running advanced RDK CPE tests..."
echo "-------------------------------------"
if pytest --board-name=rdk_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_rdk_cpe.py -v --tb=short --durations=0; then
    echo "✅ Advanced RDK CPE tests passed"
else
    echo "❌ Advanced RDK CPE tests failed or device unavailable"
fi
echo

echo "🔍 Running plugin verification tests..."
echo "---------------------------------------"
if pytest --board-name=rpi_cpe_1 --env-config=env_config.json --inventory-config=inventory.json tests/tests_plugin_verification.py -v --tb=short; then
    echo "✅ Plugin verification tests passed"
else
    echo "❌ Plugin verification tests failed"
fi
echo

echo "=========================================="
echo "Test suite completed!"
echo "=========================================="
echo
echo "📋 Test Summary:"
echo "  • Basic tests: Pure pytest functionality"
echo "  • Simple RPI CPE: Basic device operations"  
echo "  • Advanced RDK CPE: Full boardfarm3 template implementation"
echo "  • Plugin verification: Boardfarm integration tests"
echo
echo "💡 Tips:"
echo "  • Use --durations=0 to see individual test timing"
echo "  • Use -m 'not slow' to skip slow tests"
echo "  • Update inventory.json with your device IP/port"