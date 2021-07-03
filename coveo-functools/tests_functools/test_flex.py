from dataclasses import dataclass
from typing import Final, Dict, Any, Optional, Union

import pytest
from coveo_functools.exceptions import AmbiguousAnnotation
from coveo_functools.flex import flex, RAW_KEY
from coveo_testing.markers import UnitTest


@UnitTest
def test_flex_factory_detect_and_recurse_objects() -> None:
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
    assert not hasattr(leaf, "stripped")
    assert isinstance(leaf, MockLeaf)


@UnitTest
def test_flex_factory_raw() -> None:
    """The raw data is injected inside the instance."""

    class MockTest:
        raw: Dict[str, Any]

        def __init__(self, test: str) -> None:
            self.test = test

    payload = {"_test": "raw"}
    instance = flex(MockTest)(**payload)
    assert getattr(instance, RAW_KEY) == payload


@UnitTest
def test_flex_factory_raw_constructor() -> None:
    """If the raw key is in the constructor, use it."""

    @dataclass
    class MockTest:
        test: str
        _flexed_from_: Dict[str, Any]

    payload = {"_test": "raw"}
    instance = flex(MockTest)(**payload)
    assert instance._flexed_from_ == payload


@UnitTest
def test_flex_factory_unions() -> None:
    @dataclass
    class MockUnion:
        union: Optional[Union[bool, float]]

    assert flex(MockUnion)(**{"union": True}).union is True
    assert flex(MockUnion)(**{"union": 1.2}).union == 1.2
    assert flex(MockUnion)(**{"union": None}).union is None


@UnitTest
def test_flex_factory_invalid_union() -> None:
    """Unions must be comprised of select builtin types only, else it may become ambiguous."""

    @dataclass
    class MockUnion:
        union: Union[str, object]

    with pytest.raises(AmbiguousAnnotation):
        _ = flex(MockUnion)(**{"union": "sorry"})


@UnitTest
def test_flex_factory_defaults() -> None:
    @dataclass
    class MockUnion:
        none: Optional[str] = None
        not_none: Optional[str] = "set"

    assert flex(MockUnion)().none is None
    assert flex(MockUnion)().not_none is not None


@UnitTest
def test_flex_factory_raise_not_set() -> None:
    @dataclass
    class MockUnion:
        missing: Optional[str]

    with pytest.raises(TypeError):
        _ = flex(MockUnion)()


@UnitTest
def test_flex_factory_decorator_class() -> None:
    @flex
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"


@UnitTest
def test_flex_factory_decorator_class_alt() -> None:
    @flex()
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"


@UnitTest
def test_flex_factory_decorator_alt_with_params() -> None:
    @flex()
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"


@UnitTest
def test_flex_factory_decorator_dataclass() -> None:
    @flex
    @dataclass
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"


@UnitTest
def test_flex_factory_decorator_dataclass_alt() -> None:
    @flex()
    @dataclass
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"


@UnitTest
def test_flex_factory_decorator_function() -> None:
    @flex
    def fn(arg1: str) -> str:
        return arg1

    assert fn(**{"ARG1": "yay"}) == "yay"


@UnitTest
def test_flex_factory_decorator_function_alt() -> None:
    @flex()
    def fn(arg1: str) -> str:
        return arg1

    assert fn(**{"ARG1": "yay"}) == "yay"


@UnitTest
def test_flex_factory_decorator_method() -> None:
    @dataclass
    class Test:
        value: str

        @flex
        def method1(self, arg: str) -> str:
            return self.value + arg

    assert Test("he").method1(**{"ARG": "llo"}) == "hello"


@UnitTest
def test_flex_factory_decorator_method_alt() -> None:
    @dataclass
    class Test:
        value: str

        @flex()
        def method1(self, arg: str) -> str:
            return self.value + arg

    assert Test("he").method1(**{"ARG": "llo"}) == "hello"


def test_flex_factory_normal_use() -> None:
    @dataclass
    class Test:
        value: str

        @flex()
        def method1(self, arg: str) -> str:
            return self.value + arg

    assert Test("he").method1("llo") == "hello"
    assert Test(value="he").method1(arg="llo") == "hello"
