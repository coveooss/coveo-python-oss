from dataclasses import dataclass
from typing import Final, Dict, Any, Optional, Union

import pytest
from coveo_functools.exceptions import InvalidUnion
from coveo_functools.flex import FlexFactory
from coveo_testing.markers import UnitTest


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


@UnitTest
def test_flex_factory_detect_and_recurse_objects() -> None:
    instance = FlexFactory(MockOuter)(**MOCK_PAYLOAD)
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
    """A class can be annotated with the raw node."""

    class MockRaw:
        raw: Dict[str, Any]

        def __init__(self, test: str) -> None:
            self.test = test

    payload = {"_test": "raw"}
    instance = FlexFactory(MockRaw, keep_raw="raw")(**payload)
    assert instance.raw == payload


@UnitTest
def test_flex_factory_raw_dataclass() -> None:
    """A dataclass can be annotated with the raw node."""

    @dataclass
    class MockRaw:
        test: str
        raw: Dict[str, Any]

    payload = {"_test": "raw"}
    instance = FlexFactory(MockRaw, keep_raw="raw")(**payload)
    assert instance.raw == payload


@UnitTest
def test_flex_factory_raw_non_annotated() -> None:
    """The raw attribute works even when the class doesn't annotate it."""

    class MockRaw:
        def __init__(self, test: str) -> None:
            self.test = test

    payload = {"_test": "raw"}
    instance = FlexFactory(MockRaw, keep_raw="raw")(**payload)
    assert instance.raw == payload  # type: ignore[attr-defined]


@UnitTest
def test_flex_factory_raw_dataclass_non_annotated() -> None:
    """The raw attribute works even when the class doesn't annotate it."""

    @dataclass
    class MockRaw:
        test: str

    payload = {"_test": "raw"}
    instance = FlexFactory(MockRaw, keep_raw="raw")(**payload)
    assert instance.raw == payload  # type: ignore[attr-defined]


@UnitTest
def test_flex_factory_doesnt_override_explicit_raw() -> None:
    """If the raw data is explicitly given, don't overwrite it."""

    @dataclass
    class MockRaw:
        test: str

    expected = {"explicitly": "given"}
    payload = {"test": "raw", "raw_data": expected}
    instance = FlexFactory(MockRaw, keep_raw="raw_data")(**payload)

    assert instance.raw_data == expected  # type: ignore[attr-defined]


@UnitTest
def test_flex_factory_doesnt_override_explicit_raw_with_constructor() -> None:
    """If the raw data is explicitly given, don't overwrite it."""

    @dataclass
    class MockRaw:
        test: str
        raw_data: Dict[str, Any]

    expected = {"explicitly": "given"}
    payload = {"test": "raw", "raw_data": expected}
    instance = FlexFactory(MockRaw, keep_raw="raw_data")(**payload)

    assert instance.raw_data == expected


@UnitTest
def test_flex_factory_unions() -> None:
    @dataclass
    class MockUnion:
        union: Optional[Union[bool, float]]

    assert FlexFactory(MockUnion)(**{"union": True}).union is True
    assert FlexFactory(MockUnion)(**{"union": 1.2}).union == 1.2
    assert FlexFactory(MockUnion)(**{"union": None}).union is None


@UnitTest
def test_flex_factory_invalid_union() -> None:
    """Unions must be comprised of builtin types only, else it may become ambiguous."""

    @dataclass
    class MockUnion:
        union: Union[str, MockLeaf]

    with pytest.raises(InvalidUnion):
        _ = FlexFactory(MockUnion)(**{"union": "sorry"})


@UnitTest
def test_flex_factory_defaults() -> None:
    @dataclass
    class MockUnion:
        none: Optional[str] = None
        not_none: Optional[str] = "set"

    assert FlexFactory(MockUnion)().none is None
    assert FlexFactory(MockUnion)().not_none is not None


@UnitTest
def test_flex_factory_raise_not_set() -> None:
    @dataclass
    class MockUnion:
        missing: Optional[str]

    with pytest.raises(TypeError):
        _ = FlexFactory(MockUnion)()


def test_flex_factory_decorator() -> None:
    @FlexFactory
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"


def test_flex_factory_decorator_dataclass() -> None:
    @FlexFactory
    @dataclass
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"


def test_flex_factory_decorator_alt() -> None:
    @FlexFactory()
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"


def test_flex_factory_decorator_alt_with_params() -> None:
    @FlexFactory(strip_extras=True)
    class Test:
        def __init__(self, test: str) -> None:
            self.test = test

    assert Test(**{"TEST": "SUCCESS"}).test == "SUCCESS"
