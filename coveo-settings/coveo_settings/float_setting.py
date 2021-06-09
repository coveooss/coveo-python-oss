from coveo_settings.setting_abc import Setting
from coveo_settings.annotations import ConfigValue


class FloatSetting(Setting[float]):
    """Setting that handles float values."""

    @staticmethod
    def _cast(value: ConfigValue) -> float:
        """Converts the value to a float."""
        if not isinstance(value, (str, float, int)) or isinstance(value, bool):
            raise ValueError

        return float(value)
