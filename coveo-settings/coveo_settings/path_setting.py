from os import PathLike
from pathlib import Path
from typing import Any

from coveo_settings.annotations import ConfigValue
from coveo_settings.setting_abc import Setting


class PathSetting(Setting[Path], PathLike):
    """
    Setting that converts input to a Path instance; can also be used as PathLike.

    e.g.:
        setting = PathSetting(...)

        # either a Path or None
        optional_path = setting.value

        # PathLike cannot be None; will raise if not set:
        mandatory_path = Path(setting)

        # mandatory-as-pathlike example; will raise if not set:
        os.copy(setting, '/target/')

        # str(PathSetting(...)) is exactly as doing str(Path(...)) and will raise if missing:
        assert str(setting) == str(Path(setting))
    """

    def __fspath__(self) -> str:
        """Implements PathLike: https://docs.python.org/3/library/os.html#os.PathLike."""
        self._raise_if_missing()
        return str(self.value)

    @staticmethod
    def _cast(value: ConfigValue) -> Path:
        """Converts the value to a Path."""
        return Path(value)  # type: ignore[arg-type]

    def __truediv__(self, other: Any) -> Path:
        self._raise_if_missing()
        return self.value / other  # type: ignore[no-any-return]

    def __rtruediv__(self, other: Any) -> Path:
        self._raise_if_missing()
        return other / self.value  # type: ignore[no-any-return]
