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
    class MockRaw:
        _raw: Dict[str, Any]

        def __init__(self, test: str) -> None:
            self.test = test

    payload = {'_test': 'raw'}
    instance = FlexFactory(MockRaw, keep_raw="_raw")(**payload)
    assert instance._raw == payload


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
