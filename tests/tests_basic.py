import pytest


def test_simple_addition():
    assert 2 + 2 == 4


def test_string_operations():
    name = "boardfarm"
    assert name.upper() == "BOARDFARM"
    assert len(name) == 9


@pytest.fixture
def sample_data():
    """Provides test data to tests"""
    return {"username": "admin", "password": "secret"}


def test_login(sample_data):
    # Test uses the fixture data
    assert sample_data["username"] == "admin"


@pytest.mark.parametrize("input,expected", [
    (3, 9),
    (4, 16),
    (5, 25)
])
def test_square(input, expected):
    assert input ** 2 == expected


@pytest.mark.slow
def test_performance():
    # This test takes a long time
    pass


@pytest.mark.integration
def test_database_connection():
    # Integration test
    pass
