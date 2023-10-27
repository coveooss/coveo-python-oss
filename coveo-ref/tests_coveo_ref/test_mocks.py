from typing import Any, Callable, Final, Optional, Tuple, Type
from unittest import mock
from unittest.mock import PropertyMock, Mock, MagicMock

import pytest
from coveo_ref import _PythonReference, ref
from coveo_ref.exceptions import UsageError
from coveo_testing.parametrize import parametrize
from tests_coveo_ref.mock_module import MockClass as TransitiveMockClass
from tests_coveo_ref.mock_module import (
    MockSubClass,
    RenamedClass,
    call_inner_function_from_another_module,
    call_inner_function_wrapper_from_another_module,
    return_property_from_renamed_mock_class_instance,
    return_renamed_mock_class_instance,
)
from tests_coveo_ref.mock_module.inner import (
    MockClass,
    MockClassToRename,
    inner_function,
    inner_function_wrapper,
    inner_mock_class_factory,
)
from tests_coveo_ref.mock_module import shadow_rename


MOCKED: Final[str] = "mocked"


@parametrize(
    ("target", "expected"),
    _TEST_CASES := (
        (
            inner_function,
            ((_INNER_MODULE := "tests_coveo_ref.mock_module.inner"), "inner_function", None),
        ),
        (
            MockClass.instance_function,
            (_INNER_MODULE, "MockClass", "instance_function"),
        ),
        (MockClass.classmethod, (_INNER_MODULE, "MockClass", "classmethod")),
        (MockClass.staticmethod, (_INNER_MODULE, "MockClass", "staticmethod")),
        (MockClass.property, (_INNER_MODULE, "MockClass", "property")),
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
        (__name__, ("tests_coveo_ref.test_mocks", None, None)),
    ),
)
def test_python_reference(target: Any, expected: Tuple[str, Optional[str], Optional[str]]) -> None:
    """The _PythonReference object references the original module."""
    assert (reference := _PythonReference.from_any(target)) == _PythonReference(*expected)
    _ = reference.import_symbol()


@parametrize(("target", "expected"), _TEST_CASES)
def test_ref(target: Any, expected: Tuple[str, Optional[str], Optional[str]]) -> None:
    """`ref` without a context is similar to _PythonReference."""
    assert ref(target) == (".".join(filter(bool, expected)),)


@parametrize(
    ("target", "context", "expected"),
    (
        # with a context, we automatically find the correct object
        (
            inner_function,
            inner_function_wrapper,
            "tests_coveo_ref.mock_module.inner.inner_function",
        ),
        (
            inner_function,
            call_inner_function_from_another_module,
            "tests_coveo_ref.mock_module.inner_function",
        ),
        (
            inner_function,
            call_inner_function_wrapper_from_another_module,
            "tests_coveo_ref.mock_module.inner_function",
        ),
        (
            MockClass.instance_function,
            call_inner_function_from_another_module,
            "tests_coveo_ref.mock_module.MockClass.instance_function",
        ),
        (
            MockClass.property,
            call_inner_function_from_another_module,
            "tests_coveo_ref.mock_module.MockClass.property",
        ),
        (
            MockClassToRename.instance_function,
            call_inner_function_from_another_module,
            "tests_coveo_ref.mock_module.RenamedClass.instance_function",
        ),
        (
            MockClassToRename,
            call_inner_function_from_another_module,
            "tests_coveo_ref.mock_module.RenamedClass",
        ),
        (
            # this tests the long-shot discovery of properties, with a getter we can't use and a hidden setter.
            MockClassToRename.property,
            call_inner_function_from_another_module,
            "tests_coveo_ref.mock_module.RenamedClass.property",
        ),
        # the 2 following cases test an edge case with renames
        (
            shadow_rename.inner_function,
            shadow_rename,
            "tests_coveo_ref.mock_module.shadow_rename.inner_function",
        ),
        (
            inner_function,
            shadow_rename,
            "tests_coveo_ref.mock_module.shadow_rename.renamed_else_shadowed",
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
    ("to_patch", "check"),
    ((MockClassToRename.property, return_property_from_renamed_mock_class_instance),),
)
def test_ref_property_different_module(to_patch: Any, check: Callable[[], Any]) -> None:
    """Mock a property."""
    with mock.patch(
        *ref(to_patch, context=check), new_callable=PropertyMock, return_value=MOCKED
    ) as mocked_property:
        assert check() == MOCKED
        mocked_property.assert_called_once()


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


@parametrize(
    ("to_patch", "calling_type"),
    (
        (MockClass.property, MockClass),
        (MockClass.property, MockSubClass),
        (MockClass.property, TransitiveMockClass),
        (MockSubClass.property, MockSubClass),
        (TransitiveMockClass.property, TransitiveMockClass),
        # comical example because why not
        (
            MockClass.NestedClass.DoubleNestedClass.property,
            TransitiveMockClass.NestedClass.DoubleNestedClass,
        ),
    ),
)
def test_ref_properties(to_patch: Any, calling_type: Type[MockClass]) -> None:
    """Mocking a property on a class is trivial, and works across modules."""
    with mock.patch(
        *ref(to_patch), new_callable=PropertyMock, return_value=MOCKED
    ) as mocked_property:
        assert calling_type().property == MOCKED
        mocked_property.assert_called_once()


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


@pytest.mark.parametrize("method", ("classmethod", "staticmethod"))
@pytest.mark.parametrize("as_static", ("classmethod", "staticmethod"))
def test_ref_with_mock_patch_object_classmethod(method: str, as_static: bool) -> None:
    """
    Some definitions, such as classmethods and staticmethods, are not attached to an instance. As a result, inspecting
    them yield no way to retrieve the instance like normal functions do.

    But the mock module do allow patching them on an instance-basis using `patch.object()`. In order to keep things
    refactorable, the user needs to provide the instance separately, as the context.
    """
    instance = MockClass()

    # when specifying the context when `obj=True`, the target may be the static reference (on the class definition)
    # rather than using the instance directly because it's the same object behind the scenes.
    to_patch = getattr((MockClass if as_static else instance), method)
    with mock.patch.object(
        *ref(to_patch, context=instance, obj=True), return_value=MOCKED
    ) as mocked_fn:
        assert getattr(instance, method)() == MOCKED
        mocked_fn.assert_called_once()
        # new instances are not impacted, of course
        assert getattr(MockClass(), method)() != MOCKED


@pytest.mark.skip(reason="Annotation test only.")
def test_ref_overloads() -> None:
    """This makes sure that the typing / overloads work for mypy."""

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


def test_ref_cannot_resolve_mocks() -> None:
    with pytest.raises(UsageError, match="Mocks cannot"):
        ref(Mock())

    with pytest.raises(UsageError, match="Mocks cannot"):
        ref(MagicMock())

    with pytest.raises(UsageError, match="Mocks cannot"):
        ref(MockClass.instance_function, context=MagicMock())

    with mock.patch(*ref(MockClass.instance_function)):
        with pytest.raises(UsageError, match="Mocks cannot"):
            ref(MockClass.instance_function)


@parametrize("thing", (MockClass(), MockClass, inner_function))
def test_ref_cannot_obj_without_attributes(thing: Any) -> None:
    """Check the exception raised when trying to patch an obj without an attribute."""
    with pytest.raises(UsageError, match="at least one attribute"):
        ref(thing, obj=True)


@parametrize(
    "thing",
    (
        MockClass.instance_function,
        MockClass.staticmethod,
        MockClass().staticmethod,
        MockClass.classmethod,
        MockClass().classmethod,
    ),
)
def test_ref_obj_is_global(thing: Any) -> None:
    """Check the exception raised when trying to patch an obj that would probably turn out to be global."""
    with pytest.raises(UsageError, match="Cannot resolve an instance for the context"):
        ref(thing, obj=True)
