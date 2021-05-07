import pytest

from coveo_testing.markers import UnitTest
from coveo_settings.settings import StringSetting, ValidationConfigurationError
from coveo_settings.validation import InSequence


@UnitTest
def test_validation_in_sequence_positive() -> None:
    """ Test InSequence validation """
    validation = InSequence("first", "second")

    # Positive test
    test_setting_positive = StringSetting("ut", fallback="first", validation=validation)
    assert test_setting_positive.value == "first"
    assert str(test_setting_positive) == "first"
    assert test_setting_positive.is_valid


def test_validation_in_sequence_negative() -> None:
    """ Test InSequence validation """
    validation = InSequence("first", "second")

    # Negative test
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
