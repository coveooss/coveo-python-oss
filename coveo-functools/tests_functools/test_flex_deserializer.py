from dataclasses import dataclass

import pytest
from coveo_functools.exceptions import UnsupportedAnnotation
from typing import Final, List, Any, Optional, Union, Dict, Type

from coveo_testing.parametrize import parametrize

from coveo_functools.flex import deserialize, JSON_TYPES


@dataclass
class MockType:
    value: str


DEFAULT_VALUE: Final[str] = "yup"
DEFAULT_PAYLOAD = {"value": DEFAULT_VALUE}
DEFAULT_MOCK: Final[MockType] = MockType(DEFAULT_VALUE)


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


def test_deserialize_unions_passthrough() -> None:
    """Anything from the json types will be given back without checking; this allows unions of base types."""
    union = Union[JSON_TYPES]  # type: ignore[valid-type]

    assert deserialize(DEFAULT_VALUE, hint=union) == DEFAULT_VALUE


def test_deserialize_unions_limited() -> None:
    """
    When it's not 100% builtin types, flex limits to a single type within unions.
    This may change in the future.
    """
    with pytest.raises(UnsupportedAnnotation):
        assert deserialize(DEFAULT_VALUE, hint=Union[str, MockType]) == DEFAULT_VALUE


@parametrize("hint", (Union[MockType, List[MockType]], Union[List[MockType], MockType]))
@parametrize(
    ("payload", "expected"),
    (
        (DEFAULT_PAYLOAD, DEFAULT_MOCK),
        ([DEFAULT_PAYLOAD], [DEFAULT_MOCK]),
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


@parametrize(
    "hint",
    (
        Dict[str, Any],
        Dict[int, bool],
        Dict,
        Dict[Any, Any],
        Dict[Union[str, bool], Any],
        Dict[Any, Union[bytes, MockType]],
        Dict[Optional[Union[str, int]], Optional[Union[str, MockType, Optional[bool]]]],
    ),
)
def test_deserialize_dict(hint: Type) -> None:
    """We don't do much with'em, but they gotta work!"""
    assert deserialize(DEFAULT_PAYLOAD, hint=hint) == DEFAULT_PAYLOAD
