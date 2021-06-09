from coveo_settings.setting_abc import Setting
from coveo_settings.annotations import ConfigValue


class StringSetting(Setting[str]):
    """Setting that handles string values."""

    @staticmethod
    def _cast(value: ConfigValue) -> str:
        """Converts a value to a string."""
        if not isinstance(value, (str, bool, int, float)):
            raise ValueError(f"Cannot convert objects of type {type(value)}.")

        if not isinstance(value, str):
            value = str(value)

        if not value:
            raise ValueError(f"StringSettings cannot be empty.")

        return value
