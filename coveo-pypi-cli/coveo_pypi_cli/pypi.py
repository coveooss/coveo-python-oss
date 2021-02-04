from distutils.version import Version, StrictVersion
from typing import List, Type, TypeVar, Optional

from coveo_settings.settings import StringSetting
import requests

from .exceptions import VersionException
from .versions import StrictVersionHelper


PYPI_CLI_INDEX = StringSetting("pypi.cli.index", fallback="https://pypi.org")

T = TypeVar("T", bound=Version)


class VersionExists(Exception):
    ...


def obtain_versions_from_pypi(
    package_name: str,
    index: str = str(PYPI_CLI_INDEX),
    *,
    version_class: Type[T] = StrictVersion,  # type: ignore
    oldest_first: bool = False,
) -> List[T]:
    """
    Requests all versions of a package from a pypi server.

    oldest_first: sort order
    version_class: some functionality depends on StrictVersion. LooseVersion may be used to obtain
      packages that don't follow distutils' best practices.
    """
    response = requests.get(f"{index}/pypi/{package_name}/json")
    if response.status_code == 404:
        return []  # no hits; that might be ok.
    response.raise_for_status()
    data = response.json()

    valid_versions: List[T] = []
    for version in data["releases"].keys():
        try:
            valid_versions.append(version_class(version))
        except ValueError:
            pass  # invalid under this scheme

    # no need for a generator, sorting requires all results anyway.
    try:
        return sorted(valid_versions, reverse=not oldest_first)
    except TypeError:  # happens when versions are not standard (like dev1); use str sort :shrug:
        return sorted(valid_versions, reverse=not oldest_first, key=str)


def obtain_latest_release_from_pypi(
    package: str, index: str = str(PYPI_CLI_INDEX)
) -> Optional[StrictVersion]:
    """Obtains the latest non-prerelease version from pypi."""
    official_releases = filter(
        lambda version: not version.prerelease,
        obtain_versions_from_pypi(package, version_class=StrictVersionHelper, index=index),
    )
    return next(official_releases, None)


def compute_next_version(
    package: str,
    *,
    prerelease: bool,
    minimum_version: str = "0.0.1",
    index: str = str(PYPI_CLI_INDEX),
) -> StrictVersionHelper:
    """
    Given a package, compute the next version based on what's in pypi. e.g.:
        - If 1.0.0 is the latest release version, it becomes 1.0.1 or 1.0.1a1
        - If 1.0.1a1 is the latest prerelease, it becomes 1.0.1 or 1.0.1a2

    If a minimum version is specified and is higher than the latest release, it is considered the next version to
    release. e.g.: If 1.0.0 is the minimum version and the latest is lower:
            - 1.0.0 is the next version
            - 1.0.0a1 is the next prerelease
    """
    lbound_version = StrictVersionHelper(minimum_version)
    if lbound_version.prerelease:
        raise VersionException(f"Minimum version {minimum_version} cannot be a pre-release.")
    if lbound_version < StrictVersionHelper("0.0.1"):
        raise VersionException(f"Minimum version {minimum_version} must be 0.0.1 or higher.")

    # don't bump the patch number of the minimum version, but process the prerelease bump if applicable.
    if prerelease:
        lbound_version.bump_next_prerelease(patch=False)

    latest_release = next(
        map(StrictVersionHelper, obtain_versions_from_pypi(package, index=index)), None
    )
    if latest_release is None:
        return lbound_version

    if prerelease:
        latest_release.bump_next_prerelease()
    else:
        latest_release.bump_next_release()

    return max(lbound_version, latest_release)
