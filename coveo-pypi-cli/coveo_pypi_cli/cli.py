from collections import defaultdict
from distutils.version import LooseVersion
from typing import List, Dict

import click
from coveo_styles.styles import echo, ExitWithFailure, install_pretty_exception_hook

from .exceptions import VersionExists
from .pypi import (
    obtain_versions_from_pypi,
    compute_next_version,
    obtain_latest_release_from_pypi,
    PYPI_CLI_INDEX,
)
from .versions import StrictVersionHelper


click_argument_package = click.argument("package")
click_option_index = click.option(
    "--index",
    default=str(PYPI_CLI_INDEX),
    help='The pypi index host, in the form "https://pypi.org"',
)


@click.group()
def pypi() -> None:
    install_pretty_exception_hook()


@pypi.command()
@click_argument_package
@click.argument("version")
@click_option_index
def raise_if_exists(package: str, version: str, index: str = str(PYPI_CLI_INDEX)) -> None:
    """Raise if the version already exists."""
    if version in obtain_versions_from_pypi(package, index=index):
        raise ExitWithFailure(
            suggestions='Bump the version using "poetry version major|patch|etc" and retry.'
        ) from VersionExists(f"{package}=={version}")


@pypi.command()
@click_argument_package
@click_option_index
def versions(package: str, index: str = str(PYPI_CLI_INDEX)) -> None:
    """Prints the (unsorted) versions of a package."""
    groups: Dict[str, List[LooseVersion]] = defaultdict(list)
    for loose_version in obtain_versions_from_pypi(
        package, version_class=LooseVersion, oldest_first=True, index=index
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
@click_argument_package
@click.option("--prerelease", is_flag=True, default=False)
@click.option("--minimum-version", default="0.0.1")
@click_option_index
def next_version(
    package: str,
    prerelease: bool = False,
    minimum_version: str = "0.0.1",
    index: str = str(PYPI_CLI_INDEX),
) -> None:
    """Returns the version number for this release."""
    echo.passthrough(
        compute_next_version(
            package, prerelease=prerelease, minimum_version=minimum_version, index=index
        )
    )


@pypi.command()
@click_argument_package
@click_option_index
def current_version(package: str, index: str = str(PYPI_CLI_INDEX)) -> None:
    """Returns the most recent official release version."""
    echo.passthrough(
        obtain_latest_release_from_pypi(package, index=index) or StrictVersionHelper("0.0.0")
    )
