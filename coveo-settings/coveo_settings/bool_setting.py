from coveo_settings.annotations import ConfigValue
from coveo_settings.setting_abc import Setting


class BoolSetting(Setting[bool]):
    """
    Setting that handles bool values.

    Unlike Python, the bool conversion only allows for a few specific keywords to guard against mistakes.
    For instance, empty objects (strings, lists, dicts) or None will raise an exception.
    """

    TRUE_VALUES = ("true", "yes", "1", "y")
    FALSE_VALUES = ("false", "no", "0", "n")

    @staticmethod
    def _cast(value: ConfigValue) -> bool:
        """Converts any supported value to a bool."""
        value = str(value).lower()
        if value not in BoolSetting.TRUE_VALUES + BoolSetting.FALSE_VALUES:
            raise ValueError(f"Cannot determine boolean from {value}")

        return value in BoolSetting.TRUE_VALUES
