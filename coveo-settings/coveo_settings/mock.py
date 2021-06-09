from contextlib import contextmanager
from typing import Optional, Generator
from unittest.mock import patch

from coveo_settings.annotations import ConfigValue
from coveo_settings.setting_abc import Setting


@contextmanager
def mock_config_value(
    setting: Setting, value: Optional[ConfigValue]
) -> Generator[None, None, None]:
    """Mocks a setting value during a block of code so that it always returns `value`."""
    with patch.object(setting, "_get_value", return_value=value):
        yield
