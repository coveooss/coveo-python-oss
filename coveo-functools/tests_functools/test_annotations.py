"""Tests the annotation module."""

import attr

from coveo_testing.markers import UnitTest

from coveo_functools.annotations import find_return_annotation, find_annotations


@attr.s(auto_attribs=True)
class MockDataClassBase:
    a: int = int  # type: ignore
    b: str = str  # type: ignore


@attr.s(auto_attribs=True)
class MockDataClass(MockDataClassBase):
    c: bool = bool  # type: ignore


class MockClass:
    # noinspection PyMethodMayBeStatic
    def mock_method(self, _: str) -> bytes:
        return b""


@UnitTest
def test_find_annotations() -> None:
    """Ensure we can find all the attributes of dataclasses."""
    mock = MockDataClass()
    hints = find_annotations(type(mock), globals())
    assert len(hints) == 3
    for name, typ in hints.items():
        assert getattr(mock, name) is typ


@UnitTest
def test_find_return_annotation() -> None:
    return_response_type = find_return_annotation(MockClass.mock_method, globals())
    assert return_response_type is bytes
