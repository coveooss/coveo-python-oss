from pathlib import Path

import pytest

from coveo_settings import PathSetting
from coveo_settings.annotations import ConfigValue
from coveo_settings.exceptions import TypeConversionConfigurationError, MandatoryConfigurationError

from coveo_testing.parametrize import parametrize


def test_path_setting_basic() -> None:
    assert PathSetting("test", fallback="/path/test").value == Path("/path/test")


@parametrize("path", ("/path/test", "50"))
def test_path_setting_pathlike(path: str) -> None:
    """mypy sees it, but pycharm doesn't :shrug:"""
    assert Path(PathSetting("test", fallback=path)) == Path(path)


@parametrize("path", ({"test": "foo"}, False, 50))
def test_path_setting_conversion_error(path: ConfigValue) -> None:
    with pytest.raises(TypeConversionConfigurationError):
        _ = PathSetting("test", fallback=path)


def test_path_setting_not_set() -> None:
    with pytest.raises(MandatoryConfigurationError):
        _ = Path(PathSetting("test"))


truediv_test_data = parametrize(
    ("folder", "filename"), [("/temp/folder", "foo.txt"), ("relative/paths", "../file.txt")]
)


@truediv_test_data
def test_path_truediv(folder: str, filename: str) -> None:
    assert PathSetting("test", fallback=folder) / filename == folder / Path(filename)


@truediv_test_data
def test_path_rtruediv(folder: str, filename: str) -> None:
    assert folder / PathSetting("test", fallback=filename) == Path(folder) / filename
