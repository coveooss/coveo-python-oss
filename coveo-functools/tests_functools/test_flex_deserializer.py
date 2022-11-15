import logging
from dataclasses import dataclass, InitVar
from enum import Enum
from typing import Final, List, Any, Optional, Union, Dict, Type, Tuple

import pytest
from _pytest.logging import LogCaptureFixture

from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize

from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex import deserialize, JSON_TYPES


@dataclass
class MockType:
    value: str


class MockEnum(Enum):
    OtherKey = "other-value"
    TestKey = "test-value"


DEFAULT_VALUE: Final[str] = "yup"
DEFAULT_PAYLOAD = {"value": DEFAULT_VALUE}
DEFAULT_MOCK: Final[MockType] = MockType(DEFAULT_VALUE)

DEFAULT_MAP_PAYLOAD = {"item1": DEFAULT_PAYLOAD, "item2": DEFAULT_PAYLOAD}
DEFAULT_MAP_MOCK: Final[Dict[str, MockType]] = {"item1": DEFAULT_MOCK, "item2": DEFAULT_MOCK}


@UnitTest
@parametrize(
    ("hint", "payload", "expected"),
    (
        (List[MockType], [DEFAULT_PAYLOAD], [DEFAULT_MOCK]),
        (list, [DEFAULT_PAYLOAD], [DEFAULT_PAYLOAD]),
        # Optional lists
        (Optional[List[MockType]], [DEFAULT_PAYLOAD], [DEFAULT_MOCK]),
        (
            Optional[List[MockType]],
            [DEFAULT_PAYLOAD, DEFAULT_PAYLOAD],
            [DEFAULT_MOCK, DEFAULT_MOCK],
        ),
        (Optional[List[MockType]], [], []),
        (Optional[List[MockType]], None, None),
        # List of optional MockType
        (List[Optional[MockType]], [DEFAULT_PAYLOAD], [DEFAULT_MOCK]),
        (List[Optional[MockType]], [DEFAULT_PAYLOAD, None], [DEFAULT_MOCK, None]),
        (List[Optional[MockType]], [None, DEFAULT_PAYLOAD], [None, DEFAULT_MOCK]),
        (List[Optional[MockType]], [None], [None]),
        (List[Optional[MockType]], [], []),
        # Optional lists of optional mock types
        (Optional[List[Optional[MockType]]], [None, DEFAULT_PAYLOAD], [None, DEFAULT_MOCK]),
        (Optional[List[Optional[MockType]]], None, None),
        # inception
        (List[Optional[List[Optional[MockType]]]], [[DEFAULT_PAYLOAD]], [[DEFAULT_MOCK]]),
        (
            List[Optional[List[Optional[MockType]]]],
            [None, [DEFAULT_PAYLOAD]],
            [None, [DEFAULT_MOCK]],
        ),
        (List[Optional[List[Optional[MockType]]]], [[]], [[]]),
        (List[Optional[List[Optional[MockType]]]], [], []),
    ),
)
def test_deserialize_to_list(hint: Any, payload: Any, expected: Any) -> None:
    assert deserialize(payload, hint=hint) == expected


@UnitTest
def test_deserialize_unions_passthrough() -> None:
    """Anything from the json types will be given back without checking; this allows unions of base types."""
    union = Union[JSON_TYPES]  # type: ignore[valid-type]

    assert deserialize(DEFAULT_VALUE, hint=union) == DEFAULT_VALUE


@UnitTest
def test_deserialize_unions_limited() -> None:
    """
    When it's not 100% builtin types, flex limits to a single type within unions.
    This may change in the future.
    """
    with pytest.raises(UnsupportedAnnotation):
        assert deserialize(DEFAULT_VALUE, hint=Union[str, MockType]) == DEFAULT_VALUE


@UnitTest
@parametrize("hint", (Union[MockType, List[MockType]], Union[List[MockType], MockType]))
@parametrize(
    ("payload", "expected"),
    (
        (DEFAULT_PAYLOAD, DEFAULT_MOCK),
        ([DEFAULT_PAYLOAD], [DEFAULT_MOCK]),
        ((DEFAULT_PAYLOAD, DEFAULT_PAYLOAD), [DEFAULT_MOCK, DEFAULT_MOCK]),  # tuple input
        (None, None),
        ([], []),
    ),
)
def test_deserialize_thing_or_list_of_things(hint: Type, payload: Any, expected: Any) -> None:
    """
    Some APIs will return a single map if there's one object, else a list of them.
    Such objects must be annotated with Union[Thing, List[Thing]].
    """
    assert deserialize(payload, hint=hint) == expected


@UnitTest
@parametrize(
    "hint",
    (
        Dict[str, Any],
        Dict[int, bool],
        Dict,
        Dict[Any, Any],
        Dict[Union[str, bool], Any],
        Dict[str, Optional[Union[bool, int]]],
    ),
)
def test_deserialize_dict(hint: Type) -> None:
    """We don't do much with'em, but they gotta work!"""
    assert deserialize(DEFAULT_PAYLOAD, hint=hint) == DEFAULT_PAYLOAD


@UnitTest
@parametrize(
    "hint",
    (
        Dict[str, MockType],
        Dict[Any, MockType],
        Dict[str, Optional[MockType]],
    ),
)
def test_deserialize_dict_with_custom_value_type(hint: Any) -> None:
    assert deserialize(DEFAULT_MAP_PAYLOAD, hint=hint) == DEFAULT_MAP_MOCK


@UnitTest
@parametrize(
    ("hint", "payload", "expected"),
    (
        (
            Dict[str, List[MockType]],
            {"item1": [DEFAULT_PAYLOAD, DEFAULT_PAYLOAD]},
            {"item1": [DEFAULT_MOCK, DEFAULT_MOCK]},
        ),
        (
            Dict[str, Union[List[MockType], MockType]],
            {"item1": DEFAULT_PAYLOAD},
            {"item1": DEFAULT_MOCK},
        ),
        (
            Dict[str, Union[List[MockType], MockType]],
            {"item1": [DEFAULT_PAYLOAD]},
            {"item1": [DEFAULT_MOCK]},
        ),
    ),
)
def test_deserialize_dict_complex(hint: Any, payload: Any, expected: Any) -> None:
    assert deserialize(payload, hint=hint) == expected


@UnitTest
def test_deserialize_dict_invalid_union() -> None:
    """Make sure the union rules are respected in the dict value annotation."""
    with pytest.raises(UnsupportedAnnotation):
        _ = deserialize(DEFAULT_PAYLOAD, hint=Dict[str, Union[str, MockType]])


@UnitTest
@parametrize(
    "value",
    (
        "test-value",  # exact value
        "TestValue",  # fish for value
        "test-key",  # fish for name
        "TestKey",  # exact name
    ),
)
def test_deserialize_enum(value: str) -> None:
    assert deserialize(value, hint=MockEnum) is MockEnum.TestKey


@UnitTest
def test_deserialize_enum_nested() -> None:
    @dataclass
    class SomeClass:
        test: MockEnum

    assert deserialize({"Test": "test.key"}, hint=SomeClass).test is MockEnum.TestKey


@UnitTest
def test_deserialize_enum_list() -> None:
    assert deserialize(["test-value", "TestKey", "otherkey"], hint=List[MockEnum]) == [
        MockEnum.TestKey,
        MockEnum.TestKey,
        MockEnum.OtherKey,
    ]


@UnitTest
def test_deserialize_enum_alias() -> None:
    class SomeEnum(Enum):
        Job = "job"
        Task = Job
        Status = "status"

    assert deserialize("job", hint=SomeEnum) is SomeEnum.Job
    assert deserialize("task", hint=SomeEnum) is SomeEnum.Task
    assert SomeEnum.Job is SomeEnum.Task  # it's the same picture.


@parametrize("immutable_type", (str, int, bytes, float))
def test_deserialize_immutable(immutable_type: Type) -> None:
    class SubclassImmutable(immutable_type):  # type: ignore[valid-type,misc]
        @property
        def builtin_type(self) -> Type:
            return immutable_type

    value = deserialize(1, hint=SubclassImmutable)
    assert isinstance(value, immutable_type)
    assert isinstance(value, SubclassImmutable)
    assert value.builtin_type is immutable_type


@dataclass
class TestInitVarForwardRef:
    value: bool = False
    change: "InitVar[bool]" = False

    def __post_init__(self, change: bool) -> None:
        if change:
            self.value = change


@dataclass
class TestInitVarNoTypeForwardRef:
    value: bool = False
    change: "InitVar" = False

    def __post_init__(self, change: bool) -> None:
        if change:
            self.value = change


@dataclass
class TestInitVarNoType:
    value: bool = False
    change: InitVar = False

    def __post_init__(self, change: bool) -> None:
        if change:
            self.value = change


@dataclass
class TestInitVar:
    value: bool = False
    change: InitVar[bool] = False

    def __post_init__(self, change: bool) -> None:
        if change:
            self.value = change


@parametrize(
    "cls", (TestInitVar, TestInitVarNoType, TestInitVarForwardRef, TestInitVarNoTypeForwardRef)
)
def test_deserialize_init_var(cls: Any) -> None:
    """Handle a bug with InitVar vs forward references."""
    assert deserialize({"change": True}, hint=cls).value is True


def test_deserialize_static_typing() -> None:
    """
    This is actually a static typing test to ensure that `deserialize` correctly handles the generic annotations.

    To work correctly, mypy must be ran with warnings on unused type: ignores.
    """

    def fn(value: str) -> str:
        return value

    def correct_annotations() -> None:
        """cases that correctly follow annotations"""
        assert deserialize(DEFAULT_PAYLOAD, hint=MockType).value == DEFAULT_VALUE
        assert deserialize([DEFAULT_PAYLOAD], hint=List[MockType])[0].value == DEFAULT_VALUE
        assert deserialize(DEFAULT_PAYLOAD, hint=Dict[str, Any])["value"] == DEFAULT_VALUE
        assert deserialize(fn, hint=fn)(value=DEFAULT_VALUE) == DEFAULT_VALUE

    correct_annotations()

    def broken_annotations() -> None:  # noqa
        """we don't execute this one, because it would fail."""
        # mypy sees that we may not get a list
        _ = deserialize(DEFAULT_PAYLOAD, hint=Union[List[MockType], MockType])[0].value  # type: ignore[index]

        # ...same as above, reversed.
        _ = deserialize(DEFAULT_PAYLOAD, hint=Union[List[MockType], MockType]).value  # type: ignore[attr-defined]

        # mypy rightfully complains about None not having a `.value`
        _ = deserialize(DEFAULT_PAYLOAD, hint=Optional[MockType]).value  # type: ignore[attr-defined]

        # mypy rightfully complains about MockType not having a `.name`
        _ = deserialize(DEFAULT_PAYLOAD, hint=Optional[MockType]).name  # type: ignore[attr-defined]

        def test_return() -> str:  # noqa
            # mypy rightfully complains about returning `Any` instead of str
            return deserialize(DEFAULT_PAYLOAD, hint=MockType).name  # type: ignore[attr-defined,no-any-return]

        # mypy sees that fn accepts a str, not an int
        _ = deserialize(fn, hint=fn)(fn=1)  # type:ignore[call-arg]

        # mypy sees that fn returns a str, not an int
        _ = deserialize(fn, hint=fn)(value="") / 2  # type: ignore[operator]


# the type of the payload doesn't fit the hint
_PAYLOAD_TYPE_MISMATCH: Final[Tuple[Any, ...]] = (
    ([{"x": "y"}], MockType),
    ("x", MockType),
    ({"x": "y"}, List[str]),
    (1, dict),
)

# the type of the payload is correct but the content is wrong
_PAYLOAD_CONTENT_MISMATCH: Final[Tuple[Any, ...]] = (
    ({"x": "y"}, MockType),
    ({1: 2}, MockEnum),
    (["a"], MockEnum),
)


@parametrize(("payload", "hint"), _PAYLOAD_TYPE_MISMATCH + _PAYLOAD_CONTENT_MISMATCH)
def test_deserialize_errors_raise(payload: Any, hint: Any) -> None:
    with pytest.raises(Exception):
        _ = deserialize(payload, hint=hint, errors="raise")


@parametrize(("payload", "hint"), _PAYLOAD_TYPE_MISMATCH + _PAYLOAD_CONTENT_MISMATCH)
def test_deserialize_errors_ignore(payload: Any, hint: Any, caplog: LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        assert deserialize(payload, hint=hint, errors="ignore") == payload

    assert "Traceback" in caplog.text


@parametrize(("payload", "hint"), _PAYLOAD_TYPE_MISMATCH + _PAYLOAD_CONTENT_MISMATCH)
def test_deserialize_errors_silent(payload: Any, hint: Any, caplog: LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        assert deserialize(payload, hint=hint, errors="silent") == payload

    assert "Traceback" not in caplog.text


@parametrize(("payload", "hint"), _PAYLOAD_TYPE_MISMATCH)
def test_deserialize_errors_deprecated_type_mismatch(
    payload: Any, hint: Any, caplog: LogCaptureFixture
) -> None:
    """The legacy behavior returned the value when the type didn't match."""
    with caplog.at_level(logging.ERROR):
        assert deserialize(payload, hint=hint, errors="deprecated") == payload

    assert "Traceback" in caplog.text


@parametrize(("payload", "hint"), _PAYLOAD_CONTENT_MISMATCH)
def test_deserialize_errors_deprecated_content_mismatch(
    payload: Any, hint: Any, caplog: LogCaptureFixture
) -> None:
    """The legacy behavior would not handle the TypeError that occurs
    when the value's type is correct but its content is wrong."""
    with caplog.at_level(logging.ERROR), pytest.raises(TypeError):
        _ = deserialize(payload, hint=hint, errors="deprecated")
