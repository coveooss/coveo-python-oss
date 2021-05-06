""" Tests the settings classes. """

from typing import Any, Type
import json
import os

import pytest
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize

from coveo_settings.settings import (
    mock_config_value,
    DictSetting,
    InvalidConfiguration,
    AnySetting,
    StringSetting,
    BoolSetting,
    IntSetting,
    FloatSetting,
    Setting,
    MandatoryConfigurationError,
    TypeConversionConfigurationError,
)


def _clean_environment_variable(*environment_variable_name: str) -> None:
    """ Removes one or many environment variables. """
    for variable_name in environment_variable_name:
        if variable_name in os.environ:
            del os.environ[variable_name]


@UnitTest
def test_setting_empty() -> None:
    """ Tests the empty behavior of the AnySetting class. """
    test_setting = AnySetting("ut")
    assert test_setting._fallback is None
    assert test_setting.value is None
    assert not test_setting.is_set

    with pytest.raises(MandatoryConfigurationError):
        # you cannot == a setting that doesn't exist.
        assert test_setting.__eq__(None)

    with mock_config_value(test_setting, "anything"):
        assert not test_setting.__eq__(None)
        assert test_setting == "anything"

    assert not bool(test_setting)
    assert not test_setting


@UnitTest
def test_setting_not_empty() -> None:
    """ Tests the not-empty behavior of the AnySetting class. """
    default_value = "value"
    test_setting = AnySetting("ut", fallback=default_value)
    assert test_setting._fallback == default_value
    assert test_setting.value == default_value
    assert test_setting == default_value
    assert default_value == test_setting  # both sides
    assert test_setting.is_set


@UnitTest
def test_settings_python_number_cast_error() -> None:
    """ Tests the exceptions when we cannot cast a string into a number. """
    test_setting = AnySetting("ut", fallback="not a number")
    assert test_setting.is_set

    for fn in (int, float):
        with pytest.raises(ValueError):
            fn(test_setting)

    assert bool(test_setting)
    assert test_setting


@UnitTest
def test_settings_python_number_cast() -> None:
    """ Tests the ability to cast the value to ints and floats. """
    # test a positive float
    test_setting = AnySetting("ut", fallback="12.3")
    assert test_setting.is_set
    with pytest.raises(ValueError):  # this is the default python behavior
        assert int(test_setting) == 12
    assert float(test_setting) == 12.3
    assert str(test_setting) == "12.3"
    assert bool(test_setting)

    # test 0
    test_setting = AnySetting("ut", fallback="0")
    assert test_setting.is_set
    assert int(test_setting) == 0
    assert float(test_setting) == 0.0
    assert str(test_setting) == "0"
    assert test_setting  # bool('0') is True

    # test 0 as float
    test_setting = AnySetting("ut", fallback="0.0")
    assert test_setting.is_set
    with pytest.raises(ValueError):  # basic python behavior
        assert int(test_setting) == 0
    assert float(test_setting) == 0.0
    assert str(test_setting) == "0.0"
    assert test_setting  # bool('0.0') is True

    # test -1
    test_setting = AnySetting("ut", fallback="-1")
    assert test_setting.is_set
    assert int(test_setting) == -1
    assert float(test_setting) == -1.0
    assert test_setting  # bool('-1') is True


@UnitTest
def test_settings_non_string_default() -> None:
    """ Tests the Setting's class ability to deal with non-string types. """
    # test the false number as an int
    test_setting = AnySetting("ut", fallback=0)
    assert test_setting.value == 0
    assert isinstance(test_setting.value, int)
    assert test_setting.is_set
    assert int(test_setting) == 0
    assert float(test_setting) == 0.0
    assert not test_setting  # bool(0) is False

    # test the false number as a float
    test_setting = AnySetting("ut", fallback=0.0)
    assert test_setting.value == 0.0
    assert isinstance(test_setting.value, float)
    assert test_setting.is_set
    assert int(test_setting) == 0
    assert float(test_setting) == 0.0
    assert not test_setting  # bool(0) is False

    # test a true positive int
    test_setting = AnySetting("ut", fallback=1)
    assert isinstance(test_setting.value, int)
    assert test_setting.value == 1
    assert test_setting.is_set
    assert int(test_setting) == 1
    assert float(test_setting) == 1
    assert test_setting  # bool(1) is True

    # test a true positive float
    test_setting = AnySetting("ut", fallback=-1.2)
    assert isinstance(test_setting.value, float)
    assert test_setting.value == -1.2
    assert test_setting.is_set
    assert int(test_setting) == -1
    assert float(test_setting) == -1.2
    assert test_setting  # bool(-1.2) is True

    # test bool True
    test_setting = AnySetting("ut", fallback=True)
    assert test_setting.value is True
    assert test_setting.is_set
    assert int(test_setting) == 1
    assert float(test_setting) == 1.0
    assert test_setting  # bool(True) is True

    # test bool False
    test_setting = AnySetting("ut", fallback=False)
    assert test_setting.value is False
    assert test_setting.is_set
    assert int(test_setting) == 0
    assert float(test_setting) == 0.0
    assert not test_setting  # bool(False) is False


@UnitTest
def test_setting_environment_variable() -> None:
    """ Tests the environment variable feature of the Setting class. """
    environment_variable = "ut.test.setting.environment.variable"
    if environment_variable in os.environ:
        del os.environ[environment_variable]  # pragma: no cover
    assert environment_variable not in os.environ

    test_setting = AnySetting(environment_variable)
    assert test_setting.key == environment_variable
    assert test_setting._fallback is None
    assert test_setting.value is None
    assert not test_setting.is_set
    assert not test_setting

    test_value = "environment"
    os.environ[environment_variable] = test_value
    assert test_setting
    assert test_setting == test_value
    assert test_setting.is_set
    assert test_setting.value == test_value
    assert test_setting._fallback is None

    del os.environ[environment_variable]
    assert not test_setting.is_set
    assert not test_setting


@UnitTest
def test_string_setting() -> None:
    """ Tests the behavior of the StringSetting class. """
    for unsupported_value in ("", [], {}, set(), object()):
        with pytest.raises(TypeConversionConfigurationError):
            StringSetting("ut", fallback=unsupported_value)  # type: ignore

    test_setting = StringSetting("ut")
    assert not test_setting.is_set
    assert not test_setting

    environment_variable = "ut.test.string.setting"
    _clean_environment_variable(environment_variable)
    assert environment_variable not in os.environ

    environment_value = "env"
    default_value = "not env"
    test_setting = StringSetting(environment_variable, fallback=default_value)
    assert test_setting.value == default_value
    os.environ[environment_variable] = environment_value
    assert test_setting.value == environment_value

    for fn in (int, float):
        with pytest.raises(ValueError):
            fn(test_setting)

    assert bool(test_setting)

    del os.environ[environment_variable]
    assert test_setting.value == default_value

    # try to set it to something invalid, such as an empty string
    os.environ[environment_variable] = ""
    with pytest.raises(InvalidConfiguration):
        _ = test_setting.value
    del os.environ[environment_variable]


@UnitTest
def test_string_setting_always_true() -> None:
    """ Empty strings are not supported, it's impossible to obtain a false StringSetting unless it's None. """
    true_and_false = set()
    for true_or_false in (1, 0, True, False, "1", "0", "None", "True", "False", "Yes", "No", "no"):
        assert bool(StringSetting("ut", fallback=true_or_false))  # type: ignore
        # why not validate that the AnySetting doesn't care about that?
        assert bool(AnySetting("ut", fallback=true_or_false)) == bool(true_or_false)  # type: ignore
        true_and_false.add(bool(true_or_false))

    # in python's terms, we got true and false values up there.
    assert true_and_false == {True, False}

    # ensure the empty string behavior.
    environment_variable = "ut.test.string.setting.always.true"
    _clean_environment_variable(environment_variable)
    test_setting = StringSetting(environment_variable)
    assert not test_setting
    assert test_setting.value is None
    os.environ[environment_variable] = "check"
    assert test_setting.value == "check"
    os.environ[environment_variable] = ""
    with pytest.raises(InvalidConfiguration):
        _ = bool(test_setting)
    del os.environ[environment_variable]
    assert not test_setting


@UnitTest
def test_bool_setting() -> None:
    """ Tests the behavior of the BoolSetting class. """
    environment_variable = "ut.test.bool.settings"

    # test supported True values
    for value in ("True", "trUe", "1", 1, True, "yes"):
        test_setting = BoolSetting("ut", fallback=value)  # type: ignore
        assert isinstance(test_setting.value, bool)
        assert test_setting

        # validate environment value
        test_setting = BoolSetting(environment_variable)
        _clean_environment_variable(environment_variable)
        os.environ[environment_variable] = str(value)
        assert test_setting.value is True
        assert test_setting

    # test supported False values
    for value in ("False", "falSe", "0", 0, False, "no"):
        test_setting = BoolSetting("ut", fallback=value)  # type: ignore
        assert isinstance(test_setting.value, bool)
        assert not test_setting

        # validate environment value
        test_setting = BoolSetting(environment_variable)
        _clean_environment_variable(environment_variable)
        os.environ[environment_variable] = str(value)
        assert test_setting.value is False
        assert not test_setting

    # anything else is a problem.
    for value in ("None", "-1", "0.0", "1.0", -1, 0.0, 1.0, "", [], {}):
        # validate default value
        with pytest.raises(InvalidConfiguration):
            _ = BoolSetting("ut", fallback=value)  # type: ignore

        # validate environment value
        test_setting = BoolSetting(environment_variable)
        _clean_environment_variable(environment_variable)
        os.environ[environment_variable] = str(value)
        with pytest.raises(InvalidConfiguration):
            _ = test_setting.value


@UnitTest
def test_int_setting() -> None:
    """ Tests the behavior of the int setting. """
    environment_variable = "ut.test.int.setting"

    for trueish_int in (-1, 1, 100, "-1", "1", "100"):
        test_setting = IntSetting("ut", fallback=trueish_int)  # type: ignore
        assert isinstance(test_setting.value, int)
        assert test_setting

        # test it through environment variables.
        _clean_environment_variable(environment_variable)
        test_setting = IntSetting(environment_variable)
        assert test_setting.value is None
        os.environ[environment_variable] = str(trueish_int)
        assert isinstance(test_setting.value, int)
        assert test_setting

    for falseish_int in (0, -0, "-0", "0"):
        test_setting = IntSetting("ut", fallback=falseish_int)  # type: ignore
        assert isinstance(test_setting.value, int)
        assert not test_setting
        assert test_setting.is_set

        # test it through environment variables.
        _clean_environment_variable(environment_variable)
        test_setting = IntSetting(environment_variable)
        assert test_setting.value is None
        os.environ[environment_variable] = str(falseish_int)
        assert isinstance(test_setting.value, int)
        assert not test_setting

    for not_an_int in (1.4, "-4.2", "0.0", 0.0, True, False, "hey", "", [], "true", "0x56f"):
        with pytest.raises(InvalidConfiguration):
            _ = IntSetting("ut", fallback=not_an_int)  # type: ignore

        # through environment variables now...
        _clean_environment_variable(environment_variable)
        test_setting = IntSetting(environment_variable)
        assert test_setting.value is None
        os.environ[environment_variable] = str(not_an_int)
        with pytest.raises(InvalidConfiguration):
            _ = test_setting.value


@UnitTest
def test_float_setting() -> None:
    """ Tests the behavior of the FloatSetting class. """
    environment_variable = "ut.test.float.setting"

    for trueish_float in (-1.1, 1.0, 100, 1, "-1", "-0.1", "100.0"):
        test_setting = FloatSetting("ut", fallback=trueish_float)  # type: ignore
        assert isinstance(test_setting.value, float)
        assert test_setting

        # test it through environment variables.
        _clean_environment_variable(environment_variable)
        test_setting = FloatSetting(environment_variable)
        assert test_setting.value is None
        os.environ[environment_variable] = str(trueish_float)
        assert isinstance(test_setting.value, float)
        assert test_setting

    for falseish_float in (0.0, -0.0, "-0", "0", "0.0"):
        test_setting = FloatSetting("ut", fallback=falseish_float)  # type: ignore
        assert isinstance(test_setting.value, float)
        assert not test_setting
        assert test_setting.is_set

        # test it through environment variables.
        _clean_environment_variable(environment_variable)
        test_setting = FloatSetting(environment_variable)
        assert test_setting.value is None
        os.environ[environment_variable] = str(falseish_float)
        assert isinstance(test_setting.value, float)
        assert not test_setting

    for not_a_float in ("None", True, False, "0x56f", "true", "any", [], {}, set(), bytes(1)):
        with pytest.raises(InvalidConfiguration):
            _ = FloatSetting("ut", fallback=not_a_float)  # type: ignore

        # through environment variables now...
        _clean_environment_variable(environment_variable)
        test_setting = FloatSetting(environment_variable)
        assert test_setting.value is None
        os.environ[environment_variable] = str(not_a_float)
        with pytest.raises(InvalidConfiguration):
            _ = test_setting.value


@UnitTest
def test_dict_setting() -> None:
    """ Tests the dict setting class. """
    environment_key = "ut.test.dict.setting"
    value = {"string": "JSON", "int": 3, "null": None, "bool": True}
    os.environ[environment_key] = json.dumps(value)

    setting = DictSetting(environment_key)
    assert setting.value == value
    assert len(setting) == len(value)

    _clean_environment_variable(environment_key)


@UnitTest
def test_setting_alternate_keys() -> None:
    """Settings may specify different keys."""
    env1 = "ut.test.setting.alternate.key"
    env2 = "ut.test.setting.second.key"
    main_key = "ut.test.setting.main.key"

    for env in env1, env2, main_key:
        if env in os.environ:
            del os.environ[env]

    test_setting = AnySetting(main_key, alternate_keys=(env1, env2))
    assert not test_setting.is_set

    os.environ[env1] = "42"
    assert int(test_setting) == 42

    os.environ[env2] = "find me"
    assert int(test_setting) == 42  # env1 takes precedence
    del os.environ[env1]
    assert str(test_setting) == "find me"

    os.environ[main_key] = "overriden"
    assert str(test_setting) == "overriden"  # main key takes precedence

    del os.environ[main_key]


@UnitTest
def test_setting_fallback_callable() -> None:
    setting = StringSetting("hey.you", fallback=lambda: "out there on the wall")
    assert setting.is_set
    assert "wall" in setting.value
    assert "wall" in str(setting)


@UnitTest
def test_setting_fallback_not_set() -> None:
    setting = StringSetting("hey.you", lambda: None)
    assert not setting.is_set
    assert not setting
    assert setting.value is None

    with pytest.raises(InvalidConfiguration):
        str(setting)


@UnitTest
def test_setting_fallback_lazy() -> None:
    setting = IntSetting("hey.you", lambda: "not a number")

    with pytest.raises(InvalidConfiguration):
        int(setting)

    with pytest.raises(InvalidConfiguration):
        str(setting)

    with pytest.raises(InvalidConfiguration):
        _ = setting.value

    with pytest.raises(InvalidConfiguration):
        bool(setting)


@UnitTest
def test_setting_fallback_cast() -> None:
    assert int(IntSetting("test", lambda: "1")) == 1
    assert float(FloatSetting("test", lambda: "0.1")) == 0.1
    assert DictSetting("test", lambda: '{"ut-pass": true}').value == {"ut-pass": True}


@UnitTest
def test_setting_set_value() -> None:
    setting = BoolSetting("test")
    assert not setting
    setting.value = True
    assert setting


@UnitTest
def test_setting_unset_value_resets_behavior() -> None:
    setting = StringSetting("test", fallback="foo")
    setting.value = None
    assert setting.value == "foo"


@UnitTest
def test_setting_set_value_overrides_fallback() -> None:
    setting = IntSetting("test", fallback=1)
    assert int(setting) == 1
    setting.value = 0
    assert int(setting) == 0


@UnitTest
@parametrize(
    ("klass", "raw_value", "converted_value"),
    (
        (BoolSetting, "yes", True),
        (BoolSetting, "no", False),
        (BoolSetting, None, None),
        (IntSetting, "1", 1),
    ),
)
def test_setting_set_value_cast_and_validate(
    klass: Type[Setting], raw_value: str, converted_value: Any
) -> None:
    setting = klass("test")
    setting.value = raw_value
    assert setting.value == converted_value


@UnitTest
def test_setting_sensitive() -> None:
    setting = StringSetting("any", fallback="foo", sensitive=True)
    assert setting.value == "foo"
    assert "sensitive" in repr(setting)
    assert "foo" not in repr(setting)

    setting._sensitive = False
    assert "sensitive" not in repr(setting)
    assert "foo" in repr(setting)
