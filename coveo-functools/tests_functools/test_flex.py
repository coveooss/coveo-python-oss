from dataclasses import dataclass
from typing import Final, Dict, Any, Union

from coveo_functools.flex import FlexFactory
from coveo_testing.markers import UnitTest


@dataclass
class MockLeaf:
    object_id: str
    _int: int
    _float: float
    _bool: bool


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
        }
    }
}


@UnitTest
def test_flex_factory_detect_and_recurse_objects() -> None:
    instance = FlexFactory(MockOuter)(**MOCK_PAYLOAD)
    assert instance.object_id == 'outer'
    assert instance.inner.object_id == 'inner'
    assert instance.inner.inner.object_id == 'leaf'
    assert instance.inner.inner._int == 1
    assert instance.inner.inner._float == 1.2
    assert instance.inner.inner._bool is True

    assert isinstance(instance, MockOuter)
    assert isinstance(instance.inner, MockInner)
    assert isinstance(instance.inner.inner, MockLeaf)
