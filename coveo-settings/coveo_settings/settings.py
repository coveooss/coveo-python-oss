"""
Contains classes to create application settings that can be overridden through environment variables or config files.

There are three places where a setting may be set, in order of precedence:

1. Environment variables
2. Config files
3. Default value

Environment variables separators . and _ are optional and casing is ignored. Thus, it's possible to specify
keys like `redis.host` as `REDIS_HOST`, `__REDIS...host_`, `RedisHost` or `REDISHOST`, for instance.

This module contains no setters for a good reason; they're reserved for UTs!
"""
import json
import logging
import os
from abc import abstractmethod
from contextlib import contextmanager
from copy import copy
from typing import (
    Any,
    Optional,
    Union,
    SupportsInt,
    SupportsFloat,
    Generic,
    Iterator,
    Generator,
    Collection,
    Callable,
)
from unittest.mock import patch

from .annotations import ConfigValue, T, Validation, ValidationCallback
from .validation import InSequence


log = logging.getLogger(__name__)

ENVIRONMENT_VARIABLE_SEPARATORS = "._"


class InvalidConfiguration(Exception):
    """Thrown when a setting item is badly configured."""


class TypeConversionConfigurationError(InvalidConfiguration):
    """Thrown when a setting cannot be converted to the appropriate type."""


class MandatoryConfigurationError(InvalidConfiguration):
    """Thrown when a mandatory configuration value isn't set."""


class ValidationConfigurationError(InvalidConfiguration):
    """Thrown when a value fails a custom validation."""


class ValidationCallbackError(InvalidConfiguration):
    """Thrown when a validation type is not supported."""


def _find_setting(*keys: str) -> Optional[ConfigValue]:
    """Attempts to find a variable in the environment variables. The casing, dots (.) and the underline character (_)
    are not significant. For instance, "ut.test.setting" will match "UTTESTSETTING" and also "UT_teST.._setting"."""

    def _normalize(key_: str) -> str:
        """ Returns a lowercase version of key without separators. """
        return "".join(char.lower() for char in key_ if char not in ENVIRONMENT_VARIABLE_SEPARATORS)

    if not keys:
        raise InvalidConfiguration("Key should not be empty.")

    for potential_key in keys:
        return_value: Optional[str] = os.environ.get(potential_key)
        if return_value is None:
            stripped = _normalize(potential_key)
            for key, value in os.environ.items():
                if _normalize(key) == stripped:
                    return value
        else:
            return return_value

    return None


def _no_validation(_: ConfigValue) -> Optional[str]:
    """Default validation callback"""
    return None


class Setting(SupportsInt, SupportsFloat, Generic[T]):
    """
    Base class for magic type-checked settings.

    To enforce type safety and play along with mypy:
        - If the setting is required, use int/float/str/== to obtain or evaluate the value. If it's missing,
          an exception will be raised.
        - If the setting is optional, use `.value` instead: the value will be None if missing.

    Evaluating __bool__ evaluates the general python-truth of `.value`. Thus, missing is evaluated as bool(None).

    If you need to verify the presence/absence of a setting, use `is_set` instead.

    All methods read the value and raise an exception on bad formats.
    """

    def __init__(
        self,
        key: str,
        fallback: Optional[Union[ConfigValue, Callable[[], Optional[ConfigValue]]]] = None,
        alternate_keys: Optional[Collection[str]] = None,
        sensitive: bool = False,
        validation: Validation = _no_validation,
    ) -> None:
        """ Initializes a setting. """
        self._key: str = key
        self._alternate_keys: Collection[str] = alternate_keys or tuple()
        self._fallback = fallback
        self._override: Optional[ConfigValue] = None
        self._validation_callback: ValidationCallback = self._resolve_validation_callback(
            validation
        )
        self._sensitive = sensitive
        self._cache_validated: Optional[T] = None
        self._last_value: Optional[ConfigValue] = None
        # cast fallback values so that it breaks on import (e.g.: during tests)
        # however, do not trigger any callables or validation to promote a just-in-time evaluation at runtime
        if fallback is not None and not callable(fallback):
            self._cast_or_raise(fallback)

    @property
    def key(self) -> str:
        """ Return the key of this setting. """
        return self._key

    @property
    def value(self) -> Optional[T]:
        """ Returns the validated value of the setting, or None when not set. """
        value = self._get_value()
        return None if value is None else self._cast_and_validate(value)

    @value.setter
    def value(self, value: Optional[ConfigValue]) -> None:
        """Sets the value so that it overrides environment or fallback, if any.

        This is useful in CLI applications to propagate global flags such as "DryRun" or "Verbose".

        If it is `None`, the normal behavior is restored (reading from environment + fallback).
        To simulate/override as "unset", use `mock_config_value` with `None` instead.
        """
        self._override = value

    @property
    def is_set(self) -> bool:
        """
        Indicates if the value is set (values with defaults are always set unless mocked).
        This doesn't mean the value is valid.
        """
        return self._get_value() is not None

    @property
    def is_valid(self) -> bool:
        """ True if value is set and valid. """
        try:
            return self.value is not None
        except InvalidConfiguration:
            return False

    @staticmethod
    @abstractmethod
    def _cast(value: ConfigValue) -> T:
        """ Casts a value to the appropriate type. """

    def _cast_or_raise(self, value: ConfigValue) -> T:
        """ Cast the value or raise an exception. """
        try:
            return self._cast(value)
        except (TypeError, ValueError) as exception:
            raise TypeConversionConfigurationError(
                f"{self._pretty_repr(value)}: Conversion to desired type failed."
            ) from exception

    def _validate_or_raise(self, value: T) -> T:
        """ Launches the custom validation callback on a value. Raises ValidationConfigurationError on failure. """
        if self._cache_validated != value:
            error_message = self._validation_callback(value)
            if error_message:
                raise ValidationConfigurationError(f"{self._pretty_repr(value)}: {error_message}")
            self._cache_validated = copy(value)
        return value

    def _cast_and_validate(self, value: ConfigValue) -> T:
        """ Cast and validate the value or raise an exception. """
        return self._validate_or_raise(self._cast_or_raise(value))

    def _get_value(self) -> Optional[ConfigValue]:
        """Returns the raw value/fallback/override of this setting, else None."""
        value = (
            _find_setting(self.key, *self._alternate_keys)
            if self._override is None
            else self._override
        )
        if value is None and self._fallback is not None:
            value = self._fallback() if callable(self._fallback) else self._fallback

        self._last_value = copy(value)
        return value

    def _resolve_validation_callback(self, validation: Validation) -> ValidationCallback:
        if callable(validation):
            return validation

        try:
            if isinstance(validation, str):
                raise TypeError(validation)
            iterable = iter(validation)
        except TypeError as exception:
            raise ValidationCallbackError("Unsupported validation callback type") from exception

        return InSequence(*iterable)

    def _raise_if_missing(self) -> None:
        """ Raises an MandatoryConfigurationError exception if the setting is required but missing. """
        if not self.is_set:
            raise MandatoryConfigurationError(f'Mandatory config item "{self.key}" is missing.')

    def _pretty_repr(self, value: Optional[ConfigValue]) -> str:
        value_str = "<not-set>" if value is None else "<sensitive>" if self._sensitive else value
        return f"{self.__class__.__name__}[{self.key}] = {value_str}"

    def __repr__(self) -> str:
        """ Returns a readable representation of the item for debugging. """
        # we are overly careful in not triggering mechanics (e.g.: _get_value()) from here.
        # value is only shown if already computed.
        value = next(
            v for v in (self._cache_validated, self._last_value, "<not-evaluated>") if v is not None
        )
        return self._pretty_repr(value)

    def __eq__(self, other: Any) -> bool:
        """ Indicates if the value is equal to another one. """
        self._raise_if_missing()
        equal = other == self.value
        if isinstance(equal, bool):
            return equal
        return NotImplemented  # pragma: no cover

    def __bool__(self) -> bool:
        """ Indicates if the value is True (in python's terms). Missing values are False. """
        return bool(self.value)

    def __str__(self) -> str:
        """ Returns the value, blindly converted to a string. """
        self._raise_if_missing()
        return str(self.value)

    def __int__(self) -> int:
        """ Returns the value, blindly converted to int. """
        self._raise_if_missing()
        return int(self.value)  # type: ignore

    def __float__(self) -> float:
        """ Return the value, blindly converted to float. """
        self._raise_if_missing()
        return float(self.value)  # type: ignore


class AnySetting(Setting[Any]):  # pylint: disable=inherit-non-class
    """ Setting class that performs no conversion. """

    @staticmethod
    def _cast(value: ConfigValue) -> T:
        """ Always use the provided value with no conversion. """
        return value  # type: ignore


class BoolSetting(Setting[bool]):  # pylint: disable=inherit-non-class
    """
    Setting that handles bool values.

    Unlike Python, the bool conversion only allows for a few specific keywords to guard against mistakes.
    For instance, empty objects (strings, lists, dicts) or None will raise an exception.
    """

    TRUE_VALUES = ("true", "yes", "1")
    FALSE_VALUES = ("false", "no", "0")

    @staticmethod
    def _cast(value: ConfigValue) -> bool:
        """ Converts any supported value to a bool. """
        value = str(value).lower()
        if value not in BoolSetting.TRUE_VALUES + BoolSetting.FALSE_VALUES:
            raise ValueError(f"Cannot determine boolean from {value}")

        return value in BoolSetting.TRUE_VALUES


class StringSetting(Setting[str]):  # pylint: disable=inherit-non-class
    """ Setting that handles string values. """

    @staticmethod
    def _cast(value: ConfigValue) -> str:
        """ Converts a value to a string. """
        if not isinstance(value, (str, bool, int, float)):
            raise ValueError(f"Cannot convert objects of type {type(value)}.")

        if not isinstance(value, str):
            value = str(value)

        if not value:
            raise ValueError(f"StringSettings cannot be empty.")

        return value


class IntSetting(Setting[int]):  # pylint: disable=inherit-non-class
    """ Setting that handles int values. """

    @staticmethod
    def _cast(value: ConfigValue) -> int:
        """ Converts the value to an int. """
        # check for the presence of a float before converting it. This is the easiest way to catch
        # edge cases such as "0.0"
        value = str(value)
        if "." in value:
            raise ValueError
        return int(value)


class FloatSetting(Setting[float]):  # pylint: disable=inherit-non-class
    """ Setting that handles float values. """

    @staticmethod
    def _cast(value: ConfigValue) -> float:
        """ Converts the value to a float. """
        if not isinstance(value, (str, float, int)) or isinstance(value, bool):
            raise ValueError

        return float(value)


class DictSetting(Setting[dict]):  # pylint: disable=inherit-non-class
    """ Setting that handles a dictionary value. """

    def __getitem__(self, k: str) -> Any:
        """ Retrieves an item from this setting. """
        return (self.value or {})[k]

    def __len__(self) -> int:
        """ Typical dict-len. """
        return len(self.value or {})

    def __iter__(self) -> Iterator[str]:
        """ Typical dict-keys iterator. """
        return iter(self.value or {})

    @staticmethod
    def _cast(value: ConfigValue) -> dict:
        """ Converts the value to a dictionary. """
        if isinstance(value, str):
            value = json.loads(value)
        assert isinstance(value, dict)  # mypy
        return value


@contextmanager
def mock_config_value(
    setting: Setting, value: Optional[ConfigValue]
) -> Generator[None, None, None]:
    """ Mocks a setting value during a block of code so that it always returns `value`. """
    with patch.object(setting, "_get_value", return_value=value):
        yield
