import logging
from pathlib import Path
from typing import Generator
from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

from coveo_functools import wait
from coveo_systools.platforms import LINUX
from coveo_testing.markers import UnitTest
from coveo_testing.mocks import resolve_mock_target
from coveo_testing.parametrize import parametrize
from coveo_testing_extras.temporary_resource.docker_container import (
    TemporaryDockerContainerResource,
    NoSuchPort,
    get_docker_client,
    DOCKER_USE_PUBLISHED_PORTS,
)
import pytest
import requests

from test_coveo_testing_extras.markers import DockerTest


_this_run_image_name = f"docker-container-test:{uuid4()}"


class TemporaryWebServerMockContainer(TemporaryDockerContainerResource):
    """Builds a custom docker image for tests."""

    def __init__(self) -> None:
        super().__init__(_this_run_image_name, "docker-container-test")

    def _get_main_uri(self, ip_address: str) -> str:
        return f"http://{ip_address}:{self.get_published_port(80)}"

    def obtain_image(self) -> None:
        image, log_stream = self.client.images.build(
            path=str(Path(__file__).parent / "docker_image_for_tests"),
            tag=_this_run_image_name,
            nocache=True,
            rm=True,
            forcerm=True,
            pull=True,
        )
        for dict_log in log_stream:
            for log in dict_log.values():
                print(log)

    def wait_for_container_running(self, timeout: int = 30) -> None:
        super().wait_for_container_running(timeout // 2)
        wait.until(
            lambda: requests.get(self.uri).ok,
            handle_exceptions=(requests.exceptions.HTTPError, requests.exceptions.ConnectionError),
            timeout_s=timeout // 2,
        )


@pytest.fixture(scope="session")
def webserver_mock_image() -> Generator[None, None, None]:
    # it's cheap and it works.
    container = TemporaryWebServerMockContainer()
    assert not container.image_exists
    container.obtain_image()
    try:
        yield
    finally:
        container.client.images.remove(container.image_name)


@pytest.fixture
@pytest.mark.usefixtures(webserver_mock_image.__name__)
def webserver_mock_container(caplog) -> Generator[TemporaryWebServerMockContainer, None, None]:
    caplog.set_level(logging.DEBUG)
    container = TemporaryWebServerMockContainer()
    with container.auto_delete():
        container.create_resource()
        yield container


@pytest.fixture
def mock_docker_client() -> Generator[None, None, None]:
    with mock.patch(resolve_mock_target(get_docker_client())):
        yield


@DockerTest
@pytest.mark.skipif(not LINUX, reason='TODO: Need a windows dockerfile.')
def test_docker_temporary_resource_get_port(
    webserver_mock_container: TemporaryWebServerMockContainer,
) -> None:
    port = webserver_mock_container.get_published_port(80)
    assert requests.get(webserver_mock_container.uri).text.strip() == "Hello!"
    if DOCKER_USE_PUBLISHED_PORTS:
        assert port != 80  # docker docs mention that the -P switch always remaps to ephemeral ports
    else:
        assert port == 80


@DockerTest
@pytest.mark.skipif(not LINUX, reason='TODO: Need a windows dockerfile.')
@pytest.mark.skipif(not bool(DOCKER_USE_PUBLISHED_PORTS), reason="Port publishing is disabled")
def test_docker_temporary_resource_get_non_existing_port(
    webserver_mock_container: TemporaryWebServerMockContainer,
) -> None:
    with pytest.raises(NoSuchPort):
        _ = webserver_mock_container.get_published_port(81)


@UnitTest
@mock.patch(resolve_mock_target(get_docker_client))
def test_docker_temporary_resource_id(mock_get_docker_client: MagicMock) -> None:
    _ = mock_get_docker_client  # clear unused argument
    dummy_container = TemporaryDockerContainerResource("bar:latest", "foo")
    assert "foo" in str(dummy_container.container_id)
    assert "bar" not in str(dummy_container.container_id)


@UnitTest
@mock.patch(resolve_mock_target(get_docker_client))
@parametrize(
    ("image_name", "expected_region"),
    (
        ("064790157154.dkr.ecr.us-east-1.amazonaws.com/repo/image:latest", "us-east-1"),
        (".ecr.ap-southeast-2.amazonaws.com:tag", "ap-southeast-2"),  # minimal regex match
        ("docker.io/not/ecr:tag", None),
    ),
)
def test_docker_temporary_resource_ecr_region(
    mock_docker_client: MagicMock, image_name: str, expected_region: str
) -> None:
    _ = mock_docker_client  # clear unused argument warning
    assert TemporaryDockerContainerResource(image_name, "whatever").ecr_region == expected_region


@UnitTest
@mock.patch(resolve_mock_target(get_docker_client))
def test_docker_temporary_resource_no_admin_uri(mock_get_docker_client: MagicMock) -> None:
    _ = mock_get_docker_client  # clear unused argument warning
    assert TemporaryDockerContainerResource("whatever:latest", "").admin_uri is None
