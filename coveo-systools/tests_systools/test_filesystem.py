import sys
from unittest import mock

import pytest
from coveo_systools.filesystem import find_application
from coveo_testing.markers import UnitTest


@UnitTest
def test_cannot_find_application() -> None:
    with mock.patch('shutil.which', return_value=None):
        assert find_application('meh') is None


@UnitTest
def test_raise_cannot_find_application() -> None:
    with mock.patch('shutil.which', return_value=None):
        with pytest.raises(FileNotFoundError):
            _ = find_application('meh', raise_if_not_found=True)


@UnitTest
def test_find_application() -> None:
    assert find_application('python')
