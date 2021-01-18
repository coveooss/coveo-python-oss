from typing import Callable

import attr
import pytest
from coveo_testing.markers import UnitTest

from coveo_functools.casing import flexcase, unflex


class FlexMockClass:
    @flexcase
    def decorated(self, *, arg1: int, arg2: bool) -> bool:
        return arg2

    def to_delegate(self, *, arg1: int, arg2: bool) -> bool:
        return arg2

    @flexcase
    def allow_positionals(self, arg1: int, arg2: bool) -> bool:
        return arg2


@UnitTest
def _flexcase_test(mock_class: Callable) -> None:
    assert mock_class(Arg1=1, Arg2=True)
    assert mock_class(ARG1=1, Arg2=True)
    assert mock_class(ArG_1=1, Arg2=True)
    assert mock_class(_arG1=1, A___rg2_=True)
    assert mock_class(ar_g2=True, ARG_1=1)


@UnitTest
def test_flexcase_decorator_method() -> None:
    _flexcase_test(FlexMockClass().decorated)


@UnitTest
def test_flexcase_decorator_function() -> None:
    @flexcase
    def test(arg1: int, arg2: bool) -> bool:
        return arg2

    _flexcase_test(test)


@UnitTest
def test_flexcase_dataclass() -> None:
    """Ensure we can use flexcase over dataclass constructors."""
    @attr.s(auto_attribs=True)
    class MockClass:
        test: int

    with pytest.raises(TypeError):
        # noinspection PyArgumentList
        _ = MockClass(Te_St=1)  # type: ignore

    delegated = flexcase(MockClass)(Te_St=1)
    assert isinstance(delegated, MockClass) and delegated.test == 1


@UnitTest
def test_flexcase_type_errors() -> None:
    with pytest.raises(TypeError):
        flexcase(FlexMockClass().to_delegate, strip_extra=False)(arg1=1, arg2=True, too_many_args=True)

    with pytest.raises(TypeError):
        flexcase(FlexMockClass().to_delegate)(arg1=1)  # missing arg2


@UnitTest
def test_flexcase_kw_only() -> None:
    assert FlexMockClass().allow_positionals(1, True)

    with pytest.raises(TypeError):
        FlexMockClass().decorated(1, True)  # positionals are mandatory per original signature


@UnitTest
def test_flexcase_delegate() -> None:
    """Demonstrate how to delegate a call to flexcase."""
    mock = FlexMockClass()

    with pytest.raises(TypeError):
        # noinspection PyArgumentList
        mock.to_delegate(ArG1=1, ArG_2=False)  # type: ignore

    assert flexcase(mock.to_delegate)(ArG1=1, ArG_2=False) is False


@UnitTest
def test_unflex() -> None:
    mock = FlexMockClass()
    dirty = {'ArG2': False, 'a__rg1': 2, '_Extra': None}
    assert unflex(mock.to_delegate, dirty) == {'arg1': 2, 'arg2': False}
    assert unflex(mock.to_delegate, dirty, strip_extra=False) == {'arg1': 2, 'arg2': False, '_Extra': None}
