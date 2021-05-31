from typing import Optional

from coveo_settings.annotations import ConfigValue


class InSequence:
    def __init__(self, *args: ConfigValue) -> None:
        self._condition = args

    def __call__(self, value: ConfigValue) -> Optional[str]:
        if value not in self._condition:
            values = ", ".join(map(str, self._condition))
            return f"Valid values are : {values}"
        return None
