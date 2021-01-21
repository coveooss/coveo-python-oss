"""pytest bootstrap"""

from _pytest.config import Config
from coveo_testing.markers import register_markers

from test_coveo_testing_extras.markers import DockerTest


def pytest_configure(config: Config) -> None:
    """This pytest hook is ran once, before collecting tests."""
    register_markers(config, DockerTest)
