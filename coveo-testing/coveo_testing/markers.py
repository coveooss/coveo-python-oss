import pytest
from _pytest.config import Config
from _pytest.mark import MarkDecorator

UnitTest = pytest.mark.unit_test  # :sofast:
Integration = pytest.mark.integration  # interacts with the product
Interactive = (
    pytest.mark.interactive
)  # it won't work OOTB / manual steps / eye-based validations...

# Registering the markers removes pytest warnings.
AUTO_REGISTER_TEST_MARKERS = [UnitTest, Integration, Interactive]


def register_markers(config: Config, *additional_markers: MarkDecorator) -> None:
    """
    Auto registers markers into pytest to silence some warnings.

    Must be bootstrapped from conftest.py:

        def pytest_configure(config: Config) -> None:
            register_markers(config)
    """
    for marker in AUTO_REGISTER_TEST_MARKERS + list(additional_markers):
        config.addinivalue_line("markers", f"env({marker.name})")
