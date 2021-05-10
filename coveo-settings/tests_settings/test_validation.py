import pytest

from coveo_testing.markers import UnitTest
from coveo_settings.settings import (
    StringSetting,
    ValidationConfigurationError,
    IntSetting,
    FloatSetting,
    ValidationCallbackError,
)
from coveo_settings.validation import InSequence


@UnitTest
def test_validation_in_sequence_positive() -> None:
    """ Test InSequence validation """
    validation = InSequence("first", "second")

    test_setting_positive = StringSetting("ut", fallback="first", validation=validation)
    assert test_setting_positive.value == "first"
    assert str(test_setting_positive) == "first"
    assert test_setting_positive.is_valid


def test_validation_in_sequence_negative() -> None:
    """ Test InSequence validation """
    validation = InSequence("first", "second")

    test_setting_negative = StringSetting("ut", fallback="third", validation=validation)
    with pytest.raises(ValidationConfigurationError):
        test_setting_negative.value
    with pytest.raises(ValidationConfigurationError):
        str(test_setting_negative)
    assert not test_setting_negative.is_valid

    # Test sensitive value
    test_setting_sensitive = StringSetting(
        "ut", sensitive=True, fallback="third", validation=validation
    )
    with pytest.raises(ValidationConfigurationError) as excinfo:
        test_setting_sensitive.value
    assert "third" not in str(excinfo.value)


def test_validation_magic() -> None:
    assert isinstance(IntSetting("ut", validation=[1, 2, 3])._validation_callback, InSequence)


def test_validation_magic_iterable_success() -> None:
    assert FloatSetting("ut", fallback=1.0, validation=[1.0, 2, 3]).value == 1.0


def test_validation_magic_iterable_failure() -> None:
    with pytest.raises(ValidationConfigurationError):
        _ = StringSetting("ut", fallback="hey", validation=["nope"]).value


def test_validation_magic_iterable_failure_if_string() -> None:
    with pytest.raises(ValidationCallbackError):
        _ = StringSetting("ut", validation="no strings allowed")
