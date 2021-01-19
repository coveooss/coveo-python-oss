from types import FunctionType, MethodType
from typing import Any, Union

import pytest
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize

from coveo_functools.dispatch import dispatch


@dispatch()
def dispatch_test(_: Any) -> Any:
    assert False


@dispatch_test.register(FunctionType)
def dispatch_func(_: Any) -> Any:
    return FunctionType


@dispatch_test.register(MethodType)
def dispatch_method(_: Any) -> Any:
    return MethodType


class MethodTest:
    @dispatch(switch_pos=1)
    def test(self, _: Any) -> bool:
        assert False

    @test.register(str)
    def dispatch_str(self, val: str) -> str:
        return val


@UnitTest
def test_dispatch_decorate_method() -> None:
    assert MethodTest().test('test') == 'test'


@UnitTest
def test_dispatch_detect_function() -> None:
    def i_am_a_function() -> None:
        ...
    assert dispatch_test(i_am_a_function) is FunctionType


@UnitTest
def test_dispatch_detect_method() -> None:
    class Mock:
        def i_am_a_method(self) -> None:
            ...
    assert dispatch_test(Mock().i_am_a_method) is MethodType


@UnitTest
def test_dispatch_register_warning() -> None:
    """Ensure that an exception is raised if parenthesis are missing."""
    with pytest.raises(Exception):
        # noinspection PyUnresolvedReferences
        @dispatch  # type: ignore
        def boom(_: Any) -> None:
            ...


@UnitTest
@parametrize('switch_pos', [1, 'arg2'])
def test_dispatch_arg_called_with_kwarg(switch_pos: Union[int, str]) -> None:
    """Bug fix: specifying an int as switch pos prevented kw-usage."""
    @dispatch(switch_pos=switch_pos)
    def fn(arg1: str, arg2: Any) -> str:
        return 'yup'

    assert fn('', 2) == 'yup'
    assert fn(arg2=2, arg1='') == 'yup'
    assert fn('', arg2=2) == 'yup'
