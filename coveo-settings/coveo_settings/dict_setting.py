import json
from typing import Any, Iterator

from coveo_settings.annotations import ConfigValue
from coveo_settings.setting_abc import Setting


class DictSetting(Setting[dict]):
    """Setting that handles a dictionary value."""

    def __getitem__(self, k: str) -> Any:
        """Retrieves an item from this setting."""
        return (self.value or {})[k]

    def __len__(self) -> int:
        """Typical dict-len."""
        return len(self.value or {})

    def __iter__(self) -> Iterator[str]:
        """Typical dict-keys iterator."""
        return super().__iter__()

    @staticmethod
    def _cast(value: ConfigValue) -> dict:
        """Converts the value to a dictionary."""
        if isinstance(value, str):
            value = json.loads(value)
        assert isinstance(value, dict)  # mypy
        return value
