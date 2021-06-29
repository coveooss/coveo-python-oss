import json
import os
from typing import Optional, Final

import pytest
from coveo_settings.exceptions import DuplicatedScheme, TooManyRedirects, TypeConversionConfigurationError
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize

from coveo_settings import StringSetting, BoolSetting, DictSetting
from coveo_settings.annotations import ConfigValue
from coveo_settings.setting_abc import settings_adapter


TEST_RETURN_VALUE: Final[str] = "return-value::"
TEST_REGEX_ESCAPE: Final[str] = r"[\w].*"
TEST_GARBAGE: Final[str] = r"<>{}!?+-_.|^&\/()"


parametrize_scheme = parametrize("scheme", (TEST_RETURN_VALUE, TEST_REGEX_ESCAPE, TEST_GARBAGE))


@settings_adapter(TEST_REGEX_ESCAPE)
@settings_adapter(TEST_RETURN_VALUE)
@settings_adapter(TEST_GARBAGE)
def return_value_adapter(value: str) -> Optional[ConfigValue]:
    return value


@UnitTest
@parametrize_scheme
def test_setting_adapter(scheme: str) -> None:
    assert StringSetting("...", fallback=f"{scheme}foo").value == "foo"


@UnitTest
@parametrize_scheme
def test_setting_adapter_no_match(scheme: str) -> None:
    expected = f"{scheme[:-1]}foo"
    assert StringSetting("...", fallback=expected).value == expected


@UnitTest
@parametrize_scheme
def test_duplicate_scheme(scheme: str) -> None:
    with pytest.raises(DuplicatedScheme):

        @settings_adapter(scheme)
        def dummy(_: str) -> ConfigValue:
            ...


@UnitTest
def test_scheme_case_insensitive() -> None:
    assert TEST_RETURN_VALUE.islower()
    assert StringSetting("...", fallback=f"{TEST_RETURN_VALUE.upper()}foo").value == "foo"


@UnitTest
def test_builtin_redirection() -> None:
    os.environ["test-expected"] = TEST_RETURN_VALUE + "foo"
    os.environ["test-migrated"] = "env->test-expected"
    os.environ["test-redirect"] = "env->test-migrated"
    assert StringSetting("test-redirect").value == "foo"


@UnitTest
def test_too_many_redirects() -> None:
    os.environ["test-migrated"] = "env->test-redirect"
    os.environ["test-redirect"] = "env->test-migrated"

    with pytest.raises(TooManyRedirects):
        _ = StringSetting("test-redirect").value


@UnitTest
def test_redirect_not_called_on_is_set() -> None:
    called = False

    @settings_adapter("lazy-evaluated::")
    def adapter(value: str) -> Optional[str]:
        nonlocal called
        called = True
        return value

    setting = BoolSetting("...", fallback="lazy-evaluated::yes")
    assert setting.is_set
    assert not called
    assert setting.value is True
    assert called


@UnitTest
def test_adapter_may_cast_object() -> None:
    """Demonstrates that the handler may cast the value in advance."""

    @settings_adapter("return-dict::")
    def return_dict(value: str) -> Optional[ConfigValue]:
        return json.loads(value)

    value = 'return-dict::{"success": true}'
    assert DictSetting('...', fallback=value).value['success'] is True

    with pytest.raises(TypeConversionConfigurationError):
        # providing a dictionary to a BoolSetting is never a good idea!
        _ = BoolSetting('...', fallback=value).value
