from distutils.version import StrictVersion
import re
from typing import Pattern, Sequence
from unittest import mock

from coveo_testing.markers import UnitTest
from coveo_testing.mocks import resolve_mock_target
from coveo_testing.parametrize import parametrize
import pytest
import requests_mock

from coveo_pypi_cli.pypi import compute_next_version, obtain_versions_from_pypi, PYPI_CLI_INDEX
from coveo_pypi_cli.versions import StrictVersionHelper


@UnitTest
def test_next_version_basic() -> None:
    with mock.patch(
        resolve_mock_target(obtain_versions_from_pypi),
        return_value=[
            StrictVersion("1.3.6a1"),
            StrictVersion("1.3.5"),
            StrictVersion("1.0"),
            StrictVersion("0.0.5"),
            StrictVersion("0.0.1"),
        ],
    ):
        assert compute_next_version("mocked", prerelease=False) == StrictVersion("1.3.6")
        assert compute_next_version("mocked", prerelease=True) == StrictVersion("1.3.6a2")


@UnitTest
def test_new_version() -> None:
    with mock.patch(resolve_mock_target(obtain_versions_from_pypi), return_value=[]):
        assert compute_next_version("mocked", prerelease=False) == StrictVersion("0.0.1")
        assert compute_next_version("mocked", prerelease=True) == StrictVersion("0.0.1a1")


@UnitTest
def test_new_version_bump() -> None:
    with mock.patch(
        resolve_mock_target(obtain_versions_from_pypi),
        return_value=[StrictVersion("0.0.1a2"), StrictVersion("0.0.1a1")],
    ):
        assert compute_next_version("mocked", prerelease=False) == StrictVersion("0.0.1")
        assert compute_next_version("mocked", prerelease=True) == StrictVersion("0.0.1a3")


PYPI_MATCHER: Pattern = re.compile(rf"{PYPI_CLI_INDEX}/*")


@UnitTest
def test_iter_sort_404() -> None:
    with requests_mock.Mocker() as http_mock:
        http_mock.get(re.compile(str(PYPI_CLI_INDEX)), status_code=404)
        assert not list(obtain_versions_from_pypi("test"))


@UnitTest
def test_iter_sort_empty() -> None:
    with requests_mock.Mocker() as http_mock:
        http_mock.get(re.compile(str(PYPI_CLI_INDEX)), json={"releases": {}})
        assert not list(obtain_versions_from_pypi("test"))


@UnitTest
@parametrize(
    ["releases", "minimum_version", "expected_next_version", "expected_next_prerelease"],
    (
        pytest.param([], None, "0.0.1", "a1", id="empty"),
        pytest.param([], "2.0", "2.0.0", "a1", id="empty w/minimum"),  # empty set
        pytest.param(
            [StrictVersion("0.0.1")], "0.4", "0.4.0", "a1", id="simple case"
        ),  # simple case
        pytest.param(
            [  # only pre-releases
                StrictVersion("0.0.1a0"),
                StrictVersion("0.0.1a2"),
                StrictVersion("0.0.1a1"),
                StrictVersion("0.0.1a3"),
            ],
            None,
            "0.0.1",
            "a4",
            id="only pre-releases",
        ),
        pytest.param(
            [  # only pre-releases
                StrictVersion("0.0.1a0"),
                StrictVersion("0.0.1a2"),
                StrictVersion("0.0.1a1"),
                StrictVersion("0.0.1a3"),
            ],
            "0.0.4",
            "0.0.4",
            "a1",
            id="only pre-releases w/minimum",
        ),
        pytest.param(
            [  # only pre-releases, past 0.0.1
                StrictVersion("0.0.4a0"),
                StrictVersion("0.0.4a2"),
                StrictVersion("0.0.4a1"),
                StrictVersion("0.0.5a3"),
            ],
            None,
            "0.0.5",
            "a4",
            id="only pre-releases, post 0.0.1",
        ),
        pytest.param(
            [  # only pre-releases, past 0.0.1
                StrictVersion("0.0.4a0"),
                StrictVersion("0.0.4a2"),
                StrictVersion("0.0.4a1"),
                StrictVersion("0.0.5a3"),
            ],
            "0.0.3",
            "0.0.5",
            "a4",
            id="only pre-releases w/obsolete minimum",
        ),
        pytest.param(
            [  # only pre-releases, past 0.0.1
                StrictVersion("0.0.4a0"),
                StrictVersion("0.0.4a2"),
                StrictVersion("0.0.4a1"),
                StrictVersion("0.0.5a3"),
            ],
            "1.4",
            "1.4.0",
            "a1",
            id="only pre-releases w/minimum, post 0.0.1",
        ),
        pytest.param(
            [  # unordered/messy
                StrictVersion("0.0.1"),
                StrictVersion("0.2.0a4"),
                StrictVersion("0.1.9"),
                StrictVersion("0.2.1a2"),
                StrictVersion("0.0.5"),
            ],
            None,
            "0.2.1",
            "a3",
            id="unordered/messy",
        ),
        pytest.param(
            [  # no pre-release
                StrictVersion("1.10.9"),
                StrictVersion("1.10.10"),
                StrictVersion("1.9.10"),
            ],
            None,
            "1.10.11",
            "a1",
            id="no pre-releases",
        ),
        pytest.param(
            [  # target an overridden prerelease
                StrictVersion("1.10.9"),
                StrictVersion("1.10.10"),
                StrictVersion("1.10.11a1"),
                StrictVersion("1.9.10"),
            ],
            "1.10.11",
            "1.10.11",
            "a2",
            id="minimum version already has a pre-release",
        ),
    ),
)
def test_next_version(
    releases: Sequence[StrictVersion],
    minimum_version: str,
    expected_next_version: str,
    expected_next_prerelease: str,
) -> None:
    kwargs = {"minimum_version": minimum_version} if minimum_version is not None else {}
    with requests_mock.Mocker() as http_mock:
        http_mock.get(
            re.compile(PYPI_MATCHER),
            json={"releases": {str(release): None for release in releases}},
        )
        assert compute_next_version("mocked", prerelease=False, **kwargs) == StrictVersionHelper(
            expected_next_version
        )
        assert str(
            compute_next_version("mocked", prerelease=True, **kwargs)
        ) == StrictVersionHelper(expected_next_version + expected_next_prerelease)
