from copy import copy
from distutils.version import StrictVersion

import pytest
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize

from coveo_pypi_cli.versions import StrictVersionHelper


@UnitTest
def test_strict_version_helper_basic() -> None:
    version = StrictVersionHelper('1.2.3')
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3
    assert version.prerelease is None
    assert version.prerelease_stage is None
    assert version.prerelease_num is None


@UnitTest
def test_strict_version_helper_setter() -> None:
    version = StrictVersionHelper('0.0.0')
    version.major += 1
    version.minor += 2
    version.patch += 3
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3
    assert version.prerelease is None
    assert version.prerelease_stage is None
    assert version.prerelease_num is None


@UnitTest
def test_strict_version_helper_copy() -> None:
    version = StrictVersionHelper('0.0.0')
    assert version is not copy(version)
    assert version == copy(version)


@UnitTest
def test_strict_version_helper_from_strict_version() -> None:
    assert StrictVersionHelper(StrictVersion('0.0.1b5')) == StrictVersionHelper('0.0.1b5')


@UnitTest
@parametrize(('lower', 'higher'), (
        ('0.0.1', '0.0.2'),
        ('0.0.1', '0.1.1'),
        ('0.0.1', '1.0.1'),
        ('0.0.1a1', '0.0.1'),
        ('0.0.1a1', '0.0.1a2')
))
def test_strict_version_helper_compare(lower: str, higher: str) -> None:
    assert StrictVersionHelper(lower) < StrictVersionHelper(higher)
    assert StrictVersionHelper(higher) > StrictVersionHelper(lower)


@UnitTest
@parametrize(('version1', 'version2'), (
    pytest.param('0.0.1', '0.0.1', id='patch'),
    pytest.param('0.0.2a2', '0.0.2a2', id='patch prerelease'),
    pytest.param('0.2.3', '0.2.3', id='minor'),
    pytest.param('0.3.4a1', '0.3.4a1', id='minor prerelease'),
    pytest.param('1.0.4', '1.0.4', id='major'),
    pytest.param('1.0.4a76', '1.0.4a76', id='major prerelease'),
    pytest.param('10.0', '10.0.0', id='shorthand major'),
    pytest.param('3.8', '3.8.0', id='shorthand minor'),
    pytest.param('10.0a10', '10.0.0a10', id='shorthand major prerelease'),
    pytest.param('3.8a1', '3.8.0a1', id='shorthand minor prerelease'),
))
def test_strict_version_helper_equal(version1: str, version2: str) -> None:
    assert StrictVersionHelper(version1) == StrictVersionHelper(version2)


@UnitTest
@parametrize(('version1', 'version2'), (
    pytest.param('1.0.0', '2.0.0', id='different major'),
    pytest.param('0.1.0', '0.2.0', id='different minor'),
    pytest.param('0.0.1', '0.0.2', id='different patch'),
    pytest.param('0.0.1a1', '0.0.1a2', id='different prerelease'),
    pytest.param('0.0.1', '0.0.1a1', id='release vs prerelease'),
))
def test_strict_version_helper_not_equal(version1: str, version2: str) -> None:
    assert StrictVersionHelper(version1) != StrictVersionHelper(version2)


@UnitTest
@parametrize(('version', 'next_release'), (
    pytest.param('0.0.0', '0.0.1', id='initial version'),
    pytest.param('0.0.1', '0.0.2', id='patch: 0.0.1'),
    pytest.param('0.1.0', '0.1.1', id='patch: 0.1'),
    pytest.param('1.0.0', '1.0.1', id='patch: 1.0'),
    pytest.param('9.9.9', '9.9.10', id='edge: 9 -> 10'),
    pytest.param('129.659.339', '129.659.340', id='multiple digits'),
    pytest.param('0.0.1a1', '0.0.1', id='release from prerelease 0.0.1'),
    pytest.param('0.1.0a7', '0.1.0', id='release from prerelease 0.1'),
    pytest.param('1.0.0a3', '1.0.0', id='release from prerelease 1.0'),
    pytest.param('9.9.9a8', '9.9.9', id='edge prerelease: 9'),
    pytest.param('9.9.10a8', '9.9.10', id='edge prerelease: 10'),
    pytest.param('129.659.339a983', '129.659.339', id='multiple digits prerelease'),
))
def test_strict_version_helper_bump_version(version: str, next_release: str) -> None:
    version = StrictVersionHelper(version)
    version.bump_next_release()
    assert version == StrictVersionHelper(next_release)


@UnitTest
@parametrize(('version', 'next_prerelease'), (
    pytest.param('0.0.0', '0.0.1a1', id='first prerelease no releases'),
    pytest.param('0.0.1', '0.0.2a1', id='prerelease over released #1'),
    pytest.param('3.4', '3.4.1a1', id='prerelease over released #2'),
    pytest.param('0.0.1a1', '0.0.1a2', id='prerelease bump'),
    pytest.param('0.1.0a9', '0.1.0a10', id='edge: 9 -> 10'),
    pytest.param('1.0.0', '1.0.1a1', id='v1 prerelease'),
    pytest.param('1.0.0a1', '1.0a2', id='v1 prerelease bump'),
))
def test_strict_version_helper_bump_prerelease(version: str, next_prerelease: str) -> None:
    version = StrictVersionHelper(version)
    version.bump_next_prerelease()
    assert version == StrictVersionHelper(next_prerelease)
