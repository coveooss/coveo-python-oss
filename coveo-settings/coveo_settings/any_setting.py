from typing import Any

from coveo_settings.annotations import ConfigValue, T
from coveo_settings.setting_abc import Setting


class AnySetting(Setting[Any]):
    """Setting class that performs no conversion."""

    @staticmethod
    def _cast(value: ConfigValue) -> T:
        """Always use the provided value with no conversion."""
        return value  # type: ignore
