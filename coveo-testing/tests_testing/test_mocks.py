from typing import Final, Any, Tuple, Optional, Callable, Type
from unittest import mock

import pytest

from coveo_testing.parametrize import parametrize
from coveo_testing.mocks import PythonReference, ref

from tests_testing.mock_module.inner import (
    MockClass,
    inner_function,
    inner_function_wrapper,
    inner_mock_class_factory,
    MockClassToRename,
)
from tests_testing.mock_module import (
    MockClass as TransitiveMockClass,
    call_inner_function_from_another_module,
    call_inner_function_wrapper_from_another_module,
    MockSubClass,
    RenamedClass,
    return_renamed_mock_class_instance,
)

MOCKED: Final[str] = "mocked"


@parametrize(
    ("target", "expected"),
    _TEST_CASES := (
        (
            inner_function,
            ((_INNER_MODULE := "tests_testing.mock_module.inner"), "inner_function", None),
        ),
        (
            MockClass.instance_function,
            (_INNER_MODULE, "MockClass", "instance_function"),
        ),
        (MockClass.classmethod, (_INNER_MODULE, "MockClass", "classmethod")),
        (MockClass.staticmethod, (_INNER_MODULE, "MockClass", "staticmethod")),
        (MockClass, (_INNER_MODULE, "MockClass", None)),
        # this is equivalent to the previous test: the original module always prevails.
        (TransitiveMockClass, (_INNER_MODULE, "MockClass", None)),
        (
            MockClass.NestedClass.DoubleNestedClass.instance_function,
            (
                _INNER_MODULE,
                "MockClass",
                "NestedClass.DoubleNestedClass.instance_function",
            ),
        ),
        # modules as string works too
        (__name__, ("tests_testing.test_mocks", None, None)),
    ),
)
def test_python_reference(target: Any, expected: Tuple[str, Optional[str], Optional[str]]) -> None:
    """The PythonReference object references the original module."""
    assert (reference := PythonReference.from_any(target)) == PythonReference(*expected)
    _ = reference.import_symbol()


@parametrize(("target", "expected"), _TEST_CASES)
def test_ref(target: Any, expected: Tuple[str, Optional[str], Optional[str]]) -> None:
    """`ref` without a context is similar to PythonReference."""
    assert ref(target) == (".".join(filter(bool, expected)),)


@parametrize(
    ("target", "context", "expected"),
    (
        # with a context, we automatically find the correct object
        (inner_function, inner_function_wrapper, "tests_testing.mock_module.inner.inner_function"),
        (
            inner_function,
            call_inner_function_from_another_module,
            "tests_testing.mock_module.inner_function",
        ),
        (
            inner_function,
            call_inner_function_wrapper_from_another_module,
            "tests_testing.mock_module.inner_function",
        ),
        (
            MockClass.instance_function,
            call_inner_function_from_another_module,
            "tests_testing.mock_module.MockClass.instance_function",
        ),
        (
            MockClassToRename.instance_function,
            call_inner_function_from_another_module,
            "tests_testing.mock_module.RenamedClass.instance_function",
        ),
        (
            MockClassToRename,
            call_inner_function_from_another_module,
            "tests_testing.mock_module.RenamedClass",
        ),
    ),
)
def test_ref_context(target: Any, context: Any, expected: str) -> None:
    """
    `ref` with a context will fish for the symbol in context's module.
    This covers the cases where the symbol is renamed during the import.
    """
    assert ref(target, context=context) == (expected,)


@parametrize(
    ("to_patch", "check"),
    (
        (inner_function, inner_function_wrapper),
        # With a wrapper, you don't have to think about the context.
        (inner_function, call_inner_function_wrapper_from_another_module),
        (MockClass, inner_mock_class_factory),
    ),
)
def test_ref_symbol_called_from_wrapper(to_patch: Any, check: Callable[[], Any]) -> None:
    """
    Wrapping a symbol behind another callable in the same module is a clever way to make a mock work from everywhere,
    but requires changes to the source code.
    """
    with mock.patch(*ref(to_patch), return_value=MOCKED) as mocked_fn:
        assert check() == MOCKED
        mocked_fn.assert_called_once()


@parametrize(
    ("to_patch", "check"),
    (
        (inner_function, call_inner_function_from_another_module),
        (RenamedClass, return_renamed_mock_class_instance),
        # in reality, RenamedClass is MockClassToRename; it's the context that is important here.
        # same test again, but without specifying "RenamedClass".
        (MockClassToRename, return_renamed_mock_class_instance),
    ),
)
def test_ref_function_different_module(to_patch: Any, check: Callable[[], Any]) -> None:
    """In order to make a mock work for a different module, we use `context`."""
    with mock.patch(*ref(to_patch, context=check), return_value=MOCKED) as mocked_fn:
        assert check() == MOCKED
        mocked_fn.assert_called_once()


@parametrize(
    ("to_patch", "calling_type"),
    (
        (MockClass.instance_function, MockClass),
        (MockClass.instance_function, MockSubClass),
        (MockClass.instance_function, TransitiveMockClass),
        (MockSubClass.instance_function, MockSubClass),
        (TransitiveMockClass.instance_function, TransitiveMockClass),
        # comical example because why not
        (
            MockClass.NestedClass.DoubleNestedClass.instance_function,
            TransitiveMockClass.NestedClass.DoubleNestedClass,
        ),
    ),
)
def test_ref_instance_functions(to_patch: Any, calling_type: Type[MockClass]) -> None:
    """Mocking a function on a class is trivial, and works across modules."""
    with mock.patch(*ref(to_patch), return_value=MOCKED) as mocked_fn:
        assert calling_type().instance_function() == MOCKED
        mocked_fn.assert_called_once()


@parametrize("context", (__name__, test_python_reference))
def test_ref_class(context: Any) -> None:
    """
    You can patch classes directly, in order to return whatever. But the module becomes important
    again, and behaves exactly like functions at the module level.
    """
    with mock.patch(*ref(MockClass, context=context), return_value=1) as mocked_class:
        assert MockClass() == 1
        mocked_class.assert_called_once()


def test_ref_with_mock_patch_object() -> None:
    """
    In order to unpack into `mock.patch.object`, we use `obj=True`.
    It will only affect the instance passed in the target.
    """

    instance = MockClass()
    with mock.patch.object(
        *ref(instance.instance_function, obj=True), return_value=MOCKED
    ) as mocked_fn:
        assert instance.instance_function() == MOCKED
        mocked_fn.assert_called_once()

        # new instances are not impacted, of course
        assert MockClass().instance_function() != MOCKED


@pytest.mark.skip(reason="Annotation test only.")
def test_ref_overloads() -> None:
    def tuple_one_string(arg: Tuple[str]) -> None:
        ...

    def tuple_two_strings(arg: Tuple[str, str]) -> None:
        ...

    # noinspection PyUnreachableCode
    # these are the correct usages
    tuple_one_string(ref("target"))
    tuple_one_string(ref("target"))
    tuple_one_string(ref("target", context="context"))
    tuple_two_strings(ref("target", obj=True))

    # these are incorrect
    tuple_one_string(ref("target", obj=True))  # type: ignore[arg-type]
    tuple_two_strings(ref("target", context="context"))  # type: ignore[arg-type]
    tuple_two_strings(ref("target"))  # type: ignore[arg-type]
