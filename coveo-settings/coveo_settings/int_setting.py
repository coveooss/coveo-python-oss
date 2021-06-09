from coveo_settings.setting_abc import Setting
from coveo_settings.annotations import ConfigValue


class IntSetting(Setting[int]):
    """Setting that handles int values."""

    @staticmethod
    def _cast(value: ConfigValue) -> int:
        """Converts the value to an int."""
        # check for the presence of a float before converting it. This is the easiest way to catch
        # edge cases such as "0.0"
        value = str(value)
        if "." in value:
            raise ValueError
        return int(value)
