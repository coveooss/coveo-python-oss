from collections import defaultdict
from distutils.version import LooseVersion
from typing import List, Dict

import click
from coveo_styles.styles import echo, ExitWithFailure, install_pretty_exception_hook

from .exceptions import VersionExists
from .pypi import obtain_versions_from_pypi, compute_next_version, obtain_latest_release_from_pypi
from .versions import StrictVersionHelper


@click.group()
def pypi() -> None:
    install_pretty_exception_hook()


@pypi.command()
@click.argument("package")
@click.argument("version")
def raise_if_exists(package: str, version: str) -> None:
    """Raise if the version already exists."""
    if version in obtain_versions_from_pypi(package):
        raise ExitWithFailure(
            suggestions='Bump the version using "poetry version major|patch|etc" and retry.'
        ) from VersionExists(f"{package}=={version}")


@pypi.command()
@click.argument("package")
def versions(package: str) -> None:
    """Prints the (unsorted) versions of a package."""
    groups: Dict[str, List[LooseVersion]] = defaultdict(list)
    for loose_version in obtain_versions_from_pypi(
        package, version_class=LooseVersion, oldest_first=True
    ):
        version = str(loose_version)
        if "." not in version:
            groups["uncanny"].append(loose_version)
        else:
            groups[version.split(".")[0]].append(loose_version)

    for group, package_versions in groups.items():
        echo.normal(f"\nVersion {group}:")
        for loose_version in package_versions:
            echo.noise(loose_version, item=True)


@pypi.command()
@click.argument("package")
@click.option("--prerelease", is_flag=True, default=False)
@click.option("--minimum-version", default="0.0.1")
def next_version(package: str, prerelease: bool = False, minimum_version: str = "0.0.1") -> None:
    """Returns the version number for this release."""
    echo.passthrough(
        compute_next_version(package, prerelease=prerelease, minimum_version=minimum_version)
    )


@pypi.command()
@click.argument("package")
def current_version(package: str) -> None:
    """Returns the most recent official release version."""
    echo.passthrough(obtain_latest_release_from_pypi(package) or StrictVersionHelper("0.0.0"))
