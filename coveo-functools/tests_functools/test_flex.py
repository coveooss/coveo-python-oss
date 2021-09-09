from dataclasses import dataclass
from typing import Final, Dict, Any, Optional, Union, Callable, Generator, Type, Protocol

import pytest
from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex import flex, RAW_KEY
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize


@dataclass
class MockInner:
    value: str


EXPECTED_VALUE = "SUCCESS"
EXPECTED_VALUE_PAYLOAD = {"Value": EXPECTED_VALUE}
PAYLOAD: Final[Dict[str, Any]] = {"Inner": EXPECTED_VALUE_PAYLOAD}
EXPECTED_INNER: Final[MockInner] = MockInner(EXPECTED_VALUE)


def _flex_mocks() -> Generator[Any, None, None]:
    """General set of mocks meant to be called with DEFAULT_PAYLOAD."""

    @flex
    class MockClass:
        def __init__(self, inner: MockInner) -> None:
            self.inner = inner

        @flex
        def mock_method(self, inner: MockInner) -> MockInner:
            return inner

    yield MockClass
    yield MockClass(EXPECTED_INNER).mock_method

    @flex
    @dataclass
    class MockDataClass:
        inner: MockInner

    yield MockDataClass

    @flex
    def mock_function(inner: MockInner) -> MockInner:
        return inner

    yield mock_function


@UnitTest
@parametrize("obj", _flex_mocks())
def test_flex_raw_data(obj: Any) -> None:
    result = obj(**PAYLOAD)
    assert getattr(result, RAW_KEY) == PAYLOAD


@UnitTest
def test_flex_unions() -> None:
    @dataclass
    class MockUnion:
        union: Optional[Union[bool, float]]

    assert flex(MockUnion)(**{"union": True}).union is True
    assert flex(MockUnion)(**{"union": 1.2}).union == 1.2
    assert flex(MockUnion)(**{"union": None}).union is None


@UnitTest
def test_flex_invalid_union() -> None:
    """Unions must be comprised of select builtin types only, else it may become ambiguous."""

    @dataclass
    class MockUnion:
        union: Union[str, object]

    with pytest.raises(UnsupportedAnnotation):
        _ = flex(MockUnion)(**{"union": "sorry"})


@UnitTest
def test_flex_defaults() -> None:
    @dataclass
    class MockUnion:
        none: Optional[str] = None
        not_none: Optional[str] = "set"

    assert flex(MockUnion)().none is None
    assert flex(MockUnion)().not_none is not None


@UnitTest
def test_flex_raise_not_set() -> None:
    @dataclass
    class MockUnion:
        missing: Optional[str]

    with pytest.raises(TypeError):
        _ = flex(MockUnion)()


class MockInterface(Protocol):
    """Just a trick for annotations"""

    value: str

    def __init__(self, value: str) -> None:
        ...


def _class_decorator_styles() -> Generator[Type[MockInterface], None, None]:
    @flex
    class ClassNoParenthesis:
        def __init__(self, value: str) -> None:
            self.value = value

    yield ClassNoParenthesis

    @flex()
    class ClassWithParenthesis:
        def __init__(self, value: str) -> None:
            self.value = value

    yield ClassWithParenthesis

    @flex
    @dataclass
    class DataclassNoParenthesis:
        value: str

    yield DataclassNoParenthesis

    @flex()
    @dataclass
    class DataclassWithParenthesis:
        value: str

    yield DataclassWithParenthesis


@UnitTest
@parametrize("obj", _class_decorator_styles())
def test_flex_decorator_class(obj: Type[MockInterface]) -> None:
    """Ensures that different class decorator styles work with
    **, as well as direct/typical usage.
    """
    assert obj(**EXPECTED_VALUE_PAYLOAD).value == EXPECTED_VALUE
    assert obj(EXPECTED_VALUE).value == EXPECTED_VALUE


def _function_decorator_styles() -> Generator[Callable[[str], str], None, None]:
    @flex
    def no_parenthesis(value: str) -> str:
        return value

    yield no_parenthesis

    @flex()
    def with_parenthesis(value: str) -> str:
        return value

    yield with_parenthesis

    @dataclass
    class MethodNoParenthesis:
        @flex
        def method(self, value: str) -> str:
            return value

    yield MethodNoParenthesis().method

    @dataclass
    class MethodWithParenthesis:
        @flex()
        def method(self, value: str) -> str:
            return value

    yield MethodWithParenthesis().method


@UnitTest
@parametrize("fn", _function_decorator_styles())
def test_flex_function_decorator_styles(fn: Callable[..., str]) -> None:
    assert fn(**EXPECTED_VALUE_PAYLOAD) == EXPECTED_VALUE
    assert fn(EXPECTED_VALUE) == EXPECTED_VALUE


def _flex_on_flex_classes() -> Generator[Type, None, None]:
    """Flex should be able to handle flex-decorated things too."""

    @flex
    @dataclass
    class InnerDataclass:
        value: str

    @flex
    @dataclass
    class OuterDataclass:
        inner: InnerDataclass

    yield OuterDataclass

    @flex
    class InnerClass:
        def __init__(self, value: str) -> None:
            self.value = value

    @flex
    class OuterClass:
        def __init__(self, inner: InnerClass) -> None:
            self.inner = inner

    yield OuterClass


@UnitTest
@parametrize("obj", _flex_on_flex_classes())
def test_flex_on_flex(obj: Type) -> None:
    assert obj(**PAYLOAD).inner.value == EXPECTED_VALUE


@UnitTest
def test_flex_recurse_into_objects() -> None:
    @dataclass
    class MockLeaf:
        object_id: str
        _int: int
        _float: float
        _bool: Optional[bool]
        optional_str: Optional[str]

    @dataclass
    class MockInner:
        object_id: str
        inner: MockLeaf

    @dataclass
    class MockOuter:
        object_id: str
        inner: MockInner

    MOCK_PAYLOAD: Final[Dict[str, Any]] = {
        "object-id": "outer",
        "iNNer": {
            "ObjectId": "inner",
            "inner": {
                "_object__id": "leaf",
                "int": 1,
                "float": 1.2,
                "bool": True,
                "optional-str": None,
                "extra": "this value is stripped out.",
            },
        },
    }

    instance = flex(MockOuter)(**MOCK_PAYLOAD)
    assert instance.object_id == "outer"
    assert isinstance(instance, MockOuter)

    assert instance.inner.object_id == "inner"
    assert isinstance(instance.inner, MockInner)

    leaf = instance.inner.inner
    assert leaf.object_id == "leaf"
    assert leaf._int == 1
    assert leaf._float == 1.2
    assert leaf._bool is True
    assert leaf.optional_str is None
    assert not hasattr(leaf, "extra")
    assert isinstance(leaf, MockLeaf)
