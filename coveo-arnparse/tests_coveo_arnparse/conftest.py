"""pytest bootstrap"""

from _pytest.config import Config
from coveo_testing.markers import register_markers


def pytest_configure(config: Config) -> None:
    """This pytest hook is ran once, before collecting tests."""
    register_markers(config)
