from contextlib import suppress
from distutils.version import LooseVersion
import logging
import re
from typing import Tuple, Optional, Dict, Any, List
from urllib.parse import urlsplit

from coveo_functools import wait
from coveo_settings.settings import StringSetting, BoolSetting
from coveo_systools.platforms import WINDOWS, WSL
import docker
from docker import DockerClient
from docker.errors import APIError, ImageNotFound
from docker.models.images import Image
from docker.models.containers import Container

from coveo_testing.temporary_resource.unique_id import TestId
from coveo_testing.temporary_resource.base import TemporaryResource


log = logging.getLogger(__name__)

DOCKER_TIMEOUT = 30  # note: urllib timeout is not supported by the docker client.
REQUIRED_DOCKER_VERSION = LooseVersion("1.18")

DOCKER_STATIC_IP = StringSetting(
    "tests.docker.static.ip", fallback="localhost" if (WINDOWS or WSL) else None
)

# In static IP setups, we will  `--publish`  the ports and use the dynamic ports that docker attributed.
# In docker-in-docker setups, you don't need to `--publish` since you can simply ping the container ip.
DOCKER_PUBLISH_PORTS = BoolSetting("tests.docker.publish.ports", fallback=DOCKER_STATIC_IP.is_set)

# If we published, we use them by default. Some setups may want to disable this explicitly.
DOCKER_USE_PUBLISHED_PORTS = BoolSetting(
    "tests.docker.use.published.ports", fallback=bool(DOCKER_PUBLISH_PORTS)
)

LogList = List[
    Tuple[str, str]
]  # tuples contain log type and message e.g.: ('rabbitmq stderr', 'it crashed')


class ECRLogoutException(Exception):
    """ Occurs when the ECR login is expired / missing / unauthorized """


class NoSuchPort(Exception):
    """Occurs when a request is made for a port that is not exposed by the docker daemon."""


class NoSuchContainer(Exception):
    """Occurs when a request is made for a container that no longer exists."""


def _get_docker_host_version(client: DockerClient) -> LooseVersion:
    return LooseVersion(client.version()["ApiVersion"])


def get_docker_client() -> DockerClient:
    """ Returns a docker client and performs a connection/version check. """
    log.debug("Connecting to docker service")
    try:
        client: DockerClient = docker.from_env(timeout=DOCKER_TIMEOUT)
    except Exception as exception:
        raise Exception("Error while connecting to the docker daemon.") from exception

    docker_version = _get_docker_host_version(client)
    if docker_version < REQUIRED_DOCKER_VERSION:
        raise Exception(
            f'Docker version is "{docker_version}". Version "{REQUIRED_DOCKER_VERSION}" is required'
        )

    return client


class TemporaryDockerContainerResource(TemporaryResource):
    """ Class providing helper functions to manage a temporary Docker container during unit tests. """

    def __init__(self, image_name: str, friendly_name: str) -> None:
        """
        :param image_name: The image name and tag, separated with ":"
        :param friendly_name: Short and human-readable. Container name will start with this.
        """
        assert ":" in image_name
        self.client = get_docker_client()
        self.image_name: str = image_name
        self._uri: Optional[str] = None  # Client uri used to talk to the docker.
        # _extracted_logs will store the docker logs if they're requested or if the container is removed.
        self._extracted_logs: LogList = []
        self._container: Optional[Container] = None
        self._image: Optional[Image] = None
        self.container_id: TestId = TestId(friendly_name)
        log.info(self.client.info())

    @property
    def container(self) -> Container:
        """ Returns this container. """
        if not self._container:
            raise NoSuchContainer

        assert isinstance(self._container, Container)
        self._container.reload()
        return self._container

    @property
    def image(self) -> Image:
        """ Returns the image for this container."""
        if self._image is None:
            self._image = self.client.images.get(self.image_name)
        else:
            self._image.reload()
        assert self._image is not None
        return self._image

    @property
    def image_exists(self) -> bool:
        try:
            _ = self.image
        except ImageNotFound:
            return False
        return True

    @property
    def ecr_region(self) -> Optional[str]:
        """ If the image name points to an ECR registry, return the region name, else None. """
        match = re.search(r"\.ecr\.(?P<region>.+)\.amazonaws\.com", self.image_name)
        return match.group("region") if match else None

    def get_published_port(
        self, internal_port: int, protocol: str = "tcp", host_ip: str = "0.0.0.0"
    ) -> int:
        """
        Returns the external port that is mapped to the internal port for requests bound to the given host ip.
        Note: docker uses host ip 0.0.0.0 (all) unless you specified otherwise.
        """
        if not DOCKER_USE_PUBLISHED_PORTS:
            # this setup doesn't use mapped dynamic ports
            return internal_port

        port_id = f"{internal_port}/{protocol}"

        try:
            port_mappings: List[Dict[str, str]] = self.container.ports[port_id]
        except KeyError:
            raise NoSuchPort(f"{port_id} cannot be found.")

        if not port_mappings:
            raise NoSuchPort(f"{port_id} exists but is not exposed.")

        for port_mapping in port_mappings:
            if port_mapping["HostIp"] == host_ip:
                return int(port_mapping["HostPort"])

        raise NoSuchPort(f'Cannot find a {port_id} bound to {host_ip} in "{port_mappings}"')

    def create_resource(self) -> None:
        """ Creates and launch the container. """
        super().create_resource()

        if not self._container:
            if not self.image_exists:
                self.obtain_image()
            self.create_container()

        assert self._container
        log.info("Starting %s container.", self.container.name)
        self.container.start()
        log.info(self.container.attrs)

        self._uri = self._get_main_uri(self._get_ip_address())
        assert isinstance(self.uri, str) and self.uri

        log.info("Waiting for %s to start.", self.container.name)
        self.wait_for_container_running()

        log.info('%s container is started. URI="%s"', self.container.name, self.uri)
        if self.admin_uri:
            log.info('%s admin uri: "%s"', self.container.name, self.admin_uri)

    def delete_resource(self) -> None:
        """ Remove the container. """
        log.info("delete_object")
        self._extracted_logs = self.get_logs()
        self.container.remove(force=True)
        self._container = None
        self._uri = None
        super().delete_resource()

    def _get_ip_address(self) -> str:
        """ Return the local ip of the current container """
        if DOCKER_STATIC_IP:
            ip_address = str(DOCKER_STATIC_IP)
        else:
            self.container.reload()
            docker_info = self.container.attrs
            if docker_info and "NetworkSettings" in docker_info:
                ip_address = docker_info["NetworkSettings"]["IPAddress"]
            else:
                ip_address = urlsplit(self.client.api.base_url).hostname
        assert isinstance(ip_address, str) and ip_address
        return ip_address

    def create_container_arguments(self) -> Dict[str, Any]:
        """ Returns the arguments to create the docker container. """
        return dict(name=str(self.container_id), publish_all_ports=bool(DOCKER_PUBLISH_PORTS))

    def create_container(self) -> None:
        """ Create the docker container. """
        log.info('Creating container from image "%s".', self.image_name)
        self._container = self.client.containers.create(
            self.image_name, **self.create_container_arguments()
        )
        log.info('Created docker. Id="%s". Name="%s".', self.container.id, self.container.name)

    def _get_main_uri(self, ip_address: str) -> str:
        """
        Get the main URI used to talk to the server that resides in the container and set other URIs if needed.
        e.g.: Given "172.17.0.2" one may want to return "https://172.17.0.2:8080"
        """
        return ip_address

    def wait_for_container_running(self, timeout: int = 30) -> None:
        """ Wait for the docker to start. """
        wait.until(lambda: self.container.status == "running", timeout_s=timeout)

    def obtain_image(self) -> None:
        """ By default, pull the docker image from the registry. Override to specify a build process. """
        log.info('Pulling image "%s".', self.image_name)
        try:
            self.client.images.pull(self.image_name)
        except APIError as exception:  # pragma: no cover
            if exception.status_code in (404, 500) and self.ecr_region:
                raise ECRLogoutException(str(exception)) from exception
            raise

    @property
    def uri(self) -> str:
        """ Return The main URI used to talk to the server that resides in the container. """
        assert self._uri, "URI not set. Have you called create_resource?"
        return self._uri

    @property
    def admin_uri(self) -> Optional[str]:
        """ Return the URI used to administrate the service, or None if there's no admin-related uris. """
        return None

    def get_logs(self, errors_only: bool = False) -> LogList:
        """
        Returns the container's logs. Strips out debug lines by default.

        :param errors_only: True to include stderr only, False to include both stderr and stdout.
        :return: A list of (log_name, content).
        """
        logs: LogList = []
        try:
            log_filename = f"{self.container.name} stderr"
            logs.append((log_filename, self.container.logs(stdout=False)))
            if not errors_only:
                log_filename = f"{self.container.name} stdout"
                logs.append((log_filename, self.container.logs(stderr=False)))
        except Exception as exception:
            if self._extracted_logs:
                logs = self._extracted_logs
            logs.append(("stderr", str(exception)))

        return logs

    def __str__(self) -> str:
        """ Pretty-print for debuggers etc """
        with suppress(Exception):
            return f"{self.uri} [{self.image_name}]"
        return super().__str__()
