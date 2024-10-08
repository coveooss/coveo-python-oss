import logging
import sys
from dataclasses import dataclass, InitVar
from enum import Enum
from typing import Final, List, Any, Optional, Union, Dict, Type, Tuple, Literal

import pytest
from _pytest.logging import LogCaptureFixture

from coveo_functools.flex.helpers import resolve_hint
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


class MockStrEnum(str, Enum):
    OtherKey = "other-value"
    TestKey = "test-value"


class MockIntEnum(int, Enum):
    OtherKey = 1
    TestKey = 2


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
    assert deserialize(payload, hint=hint, errors="raise") == expected


@UnitTest
def test_deserialize_unions_passthrough() -> None:
    """Anything from the json types will be given back without checking; this allows unions of base types."""
    union = Union[JSON_TYPES]  # type: ignore[valid-type]

    assert deserialize(DEFAULT_VALUE, hint=union, errors="raise") == DEFAULT_VALUE


@UnitTest
def test_deserialize_unions_limited() -> None:
    """
    When it's not 100% builtin types, flex limits to a single type within unions.
    This may change in the future.
    """
    with pytest.raises(UnsupportedAnnotation):
        assert (
            deserialize(DEFAULT_VALUE, hint=Union[str, MockType], errors="raise") == DEFAULT_VALUE
        )


@UnitTest
@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python 3.10")
def test_deserialize_unions_3_10() -> None:
    # we don't parametrize because we'd have to put the whole test in an if block.
    assert deserialize(DEFAULT_VALUE, hint=str | int, errors="raise") == DEFAULT_VALUE

    assert deserialize([DEFAULT_VALUE, None], hint=list[str | int | None], errors="raise") == [
        DEFAULT_VALUE,
        None,
    ]

    assert deserialize(None, hint=list | None, errors="raise") is None

    # thing-or-list-of-things
    assert deserialize(DEFAULT_VALUE, hint=list[str] | str, errors="raise") == DEFAULT_VALUE
    assert deserialize([DEFAULT_VALUE], hint=list[str] | str | None, errors="raise") == [
        DEFAULT_VALUE
    ]
    assert deserialize(None, hint=list[str] | str | None, errors="raise") is None


@UnitTest
@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python 3.9")
def test_deserialize_list_3_9() -> None:
    """The list[str] syntax is only available in python 3.9+"""
    assert deserialize([DEFAULT_VALUE], hint=list[str], errors="raise") == [DEFAULT_VALUE]

    assert deserialize([DEFAULT_VALUE, 1], hint=list[Union[int, str]], errors="raise") == [
        DEFAULT_VALUE,
        1,
    ]


@UnitTest
@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python 3.9")
def test_deserialize_dict_3_9() -> None:
    """The dict[str] syntax is only available in python 3.9+"""
    assert deserialize({DEFAULT_VALUE: 1}, hint=dict[str, int], errors="raise") == {
        DEFAULT_VALUE: 1
    }


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
    assert deserialize(payload, hint=hint, errors="raise") == expected


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
    assert deserialize(DEFAULT_PAYLOAD, hint=hint, errors="raise") == DEFAULT_PAYLOAD


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
    assert deserialize(DEFAULT_MAP_PAYLOAD, hint=hint, errors="raise") == DEFAULT_MAP_MOCK


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
        (
            Dict[MockEnum, str],
            # matching enum values
            {"other-value": "other-value", "test-value": "test-value"},
            {MockEnum.OtherKey: "other-value", MockEnum.TestKey: "test-value"},
        ),
        (
            Dict[MockEnum, str],
            # matching enum keys, capitals and separators mismatch
            {"other-key": "other-value", "TESTKEY": "test-value"},
            {MockEnum.OtherKey: "other-value", MockEnum.TestKey: "test-value"},
        ),
        (Dict[int, str], {1: "other-value", 2: "test-value"}, {1: "other-value", 2: "test-value"}),
    ),
)
def test_deserialize_dict_complex(hint: Any, payload: Any, expected: Any) -> None:
    assert deserialize(payload, hint=hint, errors="raise") == expected


@UnitTest
def test_deserialize_dict_invalid_union() -> None:
    """Make sure the union rules are respected in the dict value annotation."""
    with pytest.raises(UnsupportedAnnotation):
        _ = deserialize(DEFAULT_PAYLOAD, hint=Dict[str, Union[str, MockType]], errors="raise")


@UnitTest
@parametrize(
    ("value", "hint"),
    (
        ("test-key", MockEnum),  # fish for enum name
        ("TestKey", MockEnum),  # fish for enum name exact match
        ("test-value", MockEnum),  # fish for enum value exact match
        ("testValue", MockEnum),  # fish for enum value
        ("test-key", MockStrEnum),  # fish for enum name
        ("TestKey", MockStrEnum),  # fish for enum name exact match
        ("test-value", MockStrEnum),  # fish for enum value exact match
        ("testValue", MockStrEnum),  # fish for enum value
        ("test-key", MockIntEnum),  # fish for enum name
        ("TestKey", MockIntEnum),  # fish for enum name exact match
        (2, MockIntEnum),  # exact match
    ),
)
def test_deserialize_enum_with_data_type(
    value: str, hint: Union[Type[MockEnum], Type[MockIntEnum], Type[MockStrEnum]]
) -> None:
    assert deserialize(value, hint=hint, errors="raise") is hint.TestKey


@parametrize(
    ["value", "hint", "expected"],
    (
        (None, Literal[None], None),
        ("foo", Literal["foo", "bar"], "foo"),
        (b"foo", Literal[b"foo", "bar"], b"foo"),
        (True, Literal[True, "vrai", "oui", 1], True),
        ("oui", Literal[True, "vrai", "oui", 1, MockEnum.TestKey], "oui"),
        ("test-value", Literal[MockEnum.TestKey], MockEnum.TestKey),
        ("test-value", Literal[MockEnum.OtherKey, 3, MockEnum.TestKey], MockEnum.TestKey),
        (3, Literal[MockEnum.OtherKey, 3, MockEnum.TestKey], 3),
        (MockEnum.OtherKey, Literal[MockEnum.OtherKey, 3, MockEnum.TestKey], MockEnum.OtherKey),
        (
            ["test-value", 3, None, False],
            List[Literal[True, False, None, 3, MockEnum.TestKey]],
            [MockEnum.TestKey, 3, None, False],
        ),
        (True, Literal[True, 1], True),
        (1, Literal[True, 1], 1),
        (0, Literal[False, 0], 0),
        (False, Literal[False, 0], False),
    ),
)
@UnitTest
def test_deserialize_literal(value: Any, hint: Any, expected: Any) -> None:
    assert deserialize(value, hint=hint, errors="raise") == expected


@UnitTest
def test_deserialize_enum_nested() -> None:
    @dataclass
    class SomeClass:
        test: MockEnum

    assert (
        deserialize({"Test": "test.key"}, hint=SomeClass, errors="raise").test is MockEnum.TestKey
    )


@UnitTest
def test_deserialize_enum_list() -> None:
    assert deserialize(
        ["test-value", "TestKey", "otherkey"], hint=List[MockEnum], errors="raise"
    ) == [
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

    assert deserialize("job", hint=SomeEnum, errors="raise") is SomeEnum.Job
    assert deserialize("task", hint=SomeEnum, errors="raise") is SomeEnum.Task
    assert SomeEnum.Job is SomeEnum.Task  # it's the same picture.


@parametrize("immutable_type", (str, int, bytes, float))
def test_deserialize_immutable(immutable_type: Type) -> None:
    class SubclassImmutable(immutable_type):
        @property
        def builtin_type(self) -> Type:
            return immutable_type

    value = deserialize(1, hint=SubclassImmutable, errors="raise")
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
    change: InitVar[Optional[bool]] = False

    def __post_init__(self, change: bool) -> None:
        if change:
            self.value = change


@parametrize(
    "cls", (TestInitVar, TestInitVarNoType, TestInitVarForwardRef, TestInitVarNoTypeForwardRef)
)
def test_deserialize_init_var(cls: Any) -> None:
    """Handle a bug with InitVar vs forward references."""
    assert deserialize({"change": True}, hint=cls, errors="raise").value is True


def test_resolve_hint_init_var() -> None:
    """
    The `InitVar` object was not created in a way that plays well with typing's `get_origin` and `get_args`
    builtins.

    More specifically:
        - get_origin returns None instead of the InitVar class
        - get_args returns nothing instead of the type between brackets (str in InitVar[str])

    As such, special handling must be done when we encounter an InitVar instance.
    """
    assert resolve_hint(InitVar[int]) == (int, [])
    # implementation detail: Optional[int] is treated as Union[int, None].
    # Also, flex removes None from Unions by design because it doesn't use it.
    assert resolve_hint(InitVar[Optional[int]]) == (Union, [int])
    assert resolve_hint(InitVar[Union[int, str]]) == (Union, [int, str])
    assert resolve_hint(InitVar) == (Any, [])
    with pytest.raises(UnsupportedAnnotation):
        resolve_hint(InitVar[int, str])  # type: ignore[misc]  # mypy actually flags this annotation error too! :)


def test_deserialize_static_typing() -> None:
    """
    This is actually a static typing test to ensure that `deserialize` correctly handles the generic annotations.

    To work correctly, mypy must be ran with warnings on unused type: ignores.
    """

    def fn(value: str) -> str:
        return value

    def correct_annotations() -> None:
        """cases that correctly follow annotations"""
        assert deserialize(DEFAULT_PAYLOAD, hint=MockType, errors="raise").value == DEFAULT_VALUE
        assert (
            deserialize([DEFAULT_PAYLOAD], hint=List[MockType], errors="raise")[0].value
            == DEFAULT_VALUE
        )
        assert (
            deserialize(DEFAULT_PAYLOAD, hint=Dict[str, Any], errors="raise")["value"]
            == DEFAULT_VALUE
        )
        assert deserialize(fn, hint=fn, errors="ignore")(value=DEFAULT_VALUE) == DEFAULT_VALUE

    correct_annotations()

    def broken_annotations() -> None:  # noqa
        """we don't execute this one, because it would fail."""
        # mypy sees that we may not get a list
        _ = deserialize(DEFAULT_PAYLOAD, hint=Union[List[MockType], MockType], errors="raise")[0].value  # type: ignore[index]

        # ...same as above, reversed.
        _ = deserialize(DEFAULT_PAYLOAD, hint=Union[List[MockType], MockType], errors="raise").value  # type: ignore[attr-defined]

        # mypy rightfully complains about None not having a `.value`
        _ = deserialize(DEFAULT_PAYLOAD, hint=Optional[MockType], errors="raise").value  # type: ignore[attr-defined]

        # mypy rightfully complains about MockType not having a `.name`
        _ = deserialize(DEFAULT_PAYLOAD, hint=Optional[MockType], errors="raise").name  # type: ignore[attr-defined]

        def test_return() -> str:  # noqa
            # mypy rightfully complains about returning `Any` instead of str
            return deserialize(DEFAULT_PAYLOAD, hint=MockType, errors="raise").name  # type: ignore[attr-defined,no-any-return]

        # mypy sees that fn accepts a str, not an int
        _ = deserialize(fn, hint=fn, errors="raise")(fn=1)  # type:ignore[call-arg]

        # mypy sees that fn returns a str, not an int
        _ = deserialize(fn, hint=fn, errors="raise")(value="") / 2  # type: ignore[operator]


# the type of the payload doesn't fit the hint
_PAYLOAD_TYPE_MISMATCH: Final[Tuple[Any, ...]] = (
    ([{"x": "y"}], MockType),
    ("x", MockType),
    ({"x": "y"}, List[str]),
    (1, dict),
    # literals are special: even if the type fits, the value may not, and we want to support that.
    # misfit enums are considered like payload mismatches.
    ("1", Literal[1]),
    (2, Literal[1]),
    ("foo", Literal["bar"]),
    # these 2 literals are even more special because True == 1 and False == 0, but we want to distinguish them.
    (False, Literal[0]),
    (True, Literal[1]),
    (True, Literal[False, 1, 0]),
    (False, Literal[True, 0, 1]),
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
    with pytest.raises(TypeError):
        _ = deserialize(payload, hint=hint, errors="deprecated")
