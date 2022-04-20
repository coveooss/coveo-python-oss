import importlib
import inspect
from dataclasses import dataclass
from unittest.mock import Mock
from types import ModuleType
from typing import Any, Tuple, Optional, Union, overload, Literal


class CannotFindSymbol(AttributeError):
    """Occurs when a symbol cannot be imported from a module."""


class DuplicateSymbol(CannotFindSymbol):
    """Occurs when a symbol occurs more than once within a module."""


@dataclass(frozen=True)
class PythonReference:
    """A helper class around resolving symbols."""

    module_name: str
    symbol_name: Optional[str] = None
    attribute_name: Optional[str] = None

    def import_module(self) -> ModuleType:
        """Import and return the module as an object."""
        return importlib.import_module(self.module_name)

    def import_symbol(self) -> Any:
        """Import and return the module and symbol. Note: The symbol of a module is the module!"""
        module = self.import_module()
        try:
            return getattr(module, self.symbol_name) if self.symbol_name else module
        except AttributeError as exception:
            raise CannotFindSymbol from exception

    def fully_qualified_name(self) -> str:
        """Returns the fully dotted name, such as `tests_testing.mock_module.inner.MockClass.inner_function`"""
        return ".".join(filter(bool, (self.module_name, self.symbol_name, self.attribute_name)))

    def with_module(self, module: Union[str, ModuleType]) -> "PythonReference":
        """Returns a new instance of PythonReference that targets the same symbol in a different module."""
        return PythonReference(
            module_name=module if isinstance(module, str) else module.__name__,
            symbol_name=self.symbol_name,
            attribute_name=self.attribute_name,
        )

    def with_name(self, name: str) -> "PythonReference":
        """Returns a new instance of PythonReference that targets a different symbol."""
        return PythonReference(
            module_name=self.module_name, symbol_name=name, attribute_name=self.attribute_name
        )

    @classmethod
    def from_any(cls, obj: Any) -> "PythonReference":
        """
        Returns a PythonReference based on an object.
        If obj is a string, it will be imported as is; therefore, it has to be a fully qualified, importable symbol.
        """
        if isinstance(obj, str):
            return cls.from_any(importlib.import_module(obj))

        if inspect.ismodule(obj):
            return cls(module_name=obj.__name__)

        qualifiers = obj.__qualname__.split(".")

        if len(qualifiers) == 1:
            # this is a symbol defined at the module level
            return cls(module_name=obj.__module__, symbol_name=qualifiers[0], attribute_name=None)

        importable = qualifiers[0] or None
        attribute = ".".join(qualifiers[1:]) or None
        return cls(module_name=obj.__module__, symbol_name=importable, attribute_name=attribute)


def _coerce(reference: PythonReference, module: Union[ModuleType, str]) -> PythonReference:
    """Find `reference` in module and return a PythonReference that points to it."""
    new_reference = reference.with_module(module if isinstance(module, str) else module.__name__)

    try:
        _ = new_reference.import_symbol()
    except CannotFindSymbol:
        # symbol was renamed? fish!
        module = new_reference.import_module()
        symbol_to_find = reference.import_symbol()
        symbols_found = tuple(
            symbol_name
            for symbol_name, symbol in module.__dict__.items()
            if symbol is symbol_to_find
        )

        if not symbols_found:
            raise  # reraise CannotFindSymbol

        if len(symbols_found) > 1:
            raise DuplicateSymbol(
                f"Duplicate symbols found for {symbol_to_find} in {module.__name__}: {symbols_found}"
            )

        return new_reference.with_name(symbols_found[0])

    return new_reference


def resolve_mock_target(target: Any) -> str:
    """

    Deprecated: You are encouraged to use `ref` instead, which can resolve a name in a target module.

    ---
    Deprecated docs:

    `mock.patch` uses a str-representation of an object to find it, but this doesn't play well with
    refactors and renames. This method extracts the str-representation of an object.

    This method will not handle _all_ kinds of objects, in which case an AttributeError will most likely be raised.

    e,g,:
     - the function `fn` on `Class` in `Module.Innner`      -> `Module.Inner.Class.fn`.
     - the function `fn` in module `Module.Inner`           -> `Module.Inner.fn`
     - the class `Class` in module `Module.Inner`           -> `Module.Inner.Class`
     - A nested class                                       -> `Module.Inner.Class.NestedClass`
     - the module `Module.Inner`                            -> `Module.Inner`

    Variables (either at the module, class or instance level) are not supported because they are passed
    by value and not by reference; they contain no metadata to inspect.
    """
    return f"{target.__module__}.{target.__name__}"


@overload
def ref(target: Any) -> Tuple[str]:
    ...


@overload
def ref(target: Any, *, context: Optional[Any]) -> Tuple[str]:
    ...


@overload
def ref(target: Any, *, obj: Literal[True]) -> Tuple[str, str]:
    ...


@overload
def ref(target: Any, *, obj: Literal[False]) -> Tuple[str]:
    ...


@overload
def ref(target: Any, *, context: Optional[Any], obj: Literal[False]) -> Tuple[str]:
    ...


# It's an error to provide `obj=True` and a context, but there was no way to express this overload at the moment.
# @overload
# def ref(target: Any, *, context: Any, obj: Literal[True]) -> Tuple[str]: ...


def ref(
    target: Any, *, context: Optional[Any] = None, obj: bool = False
) -> Union[Tuple[str], Tuple[str, str]]:
    """
    Replaces `resolves_mock_target`. Named for brevity.

    Returns a tuple meant to be unpacked into the `mock.patch` or `mock.patch.object` functions in order to enable
    refactorable mocks.

    In order to target the module where the mock will be used, use the `context` argument. It can be either:
        - A module name as a string (e.g.: "coveo_testing.logging", or __name__)
        - A symbol that belongs to the module to patch (i.e.: any function or class defined in that module)

    In order to unpack into `mock.patch.object`, set `obj=True`. The return value will
    be a tuple(object, attribute_name).

    Examples:

    How to patch a module-level symbol, such as a function or class, for any given module:

        with mock.patch(*ref(MyClass, context=fn)):
            ...

        - In this example, we want to test `fn`, which is defined in module A.
        - Module A imports `MyClass` from module B.
        - Therefore, MyClass's reference is `B.MyClass`.
        - `fn` uses MyClass.
        - If we used `mock.patch("B.MyClass")`, then it would not affect module A's namespace where `fn` resides.
        - Therefore, `fn` would still have the original B.MyClass symbol in its namespace.
        - The correct method is to use `mock.patch("A.MyClass")` even though MyClass is defined in B.
        - This is what `context` achieves. It will return the reference to `MyClass` for the namespace context of `fn`.

    How to patch a module-level symbol, such as a function or class, for the current module:

        with mock.patch(*ref(MyClass, context=__name__)):
            ...

        - In this example, the unit test imports and use `MyClass` directly, which belongs to another module.
        - Therefore, it has to provide itself as the context.
        - Therefore, use the `__name__` shortcut to provide the current module as the context.

    How to patch a function or class on an instance:

        instance = MyClass()
        with mock.patch.object(*ref(instance.fn, obj=True)):
            ...

        - In this example, we want to patch `fn` exclusively on this instance of `MyClass`.
        - To achieve this, we use the `mock.patch.object` function instead.
        - We don't need a context when using `obj=True`.
        - Therefore, the whole A vs B saga doesn't apply!
        - The `obj=True` switch will cause the return value to be (instance, "fn") in this case.
        - Therefore, the `mock.patch.object` will target the `fn` function on your instance.

    How to patch a renamed symbol / more info about `context`:

        with mock.patch(*ref(MyClass, context=fn)):

        - If you provide the context, we will inspect the context's module and fish for the object.
        - You can provide either the renamed class or the original class as the target.
        - You must provide the context where the renamed symbol can be found.
        - The context CANNOT be the renamed class. It has to be the context module, or a symbol defined within.
        - Caveat: If you happen to have the same object defined as multiple names in the same module,
          a DuplicateSymbol exception will be raised because the mock target becomes ambiguous.
    """
    if isinstance(target, Mock):
        raise Exception("Mocks cannot be resolved as a string.")

    source_reference = PythonReference.from_any(target)

    if obj:
        # Not having an attribute name would be an error for `mock.patch.object` anyway.
        assert source_reference.attribute_name

        if self := getattr(target, "__self__", None):
            # how convenient, the instance is given to us!
            return self, source_reference.attribute_name
        else:
            raise Exception("You can patch this with patch(), no need for object.")

    context_reference = PythonReference.from_any(context or target)
    target_reference = _coerce(source_reference, context_reference.module_name)

    if target_reference.attribute_name:
        # this can only be a method or property, which can be patched globally.
        return (target_reference.fully_qualified_name(),)

    # everything else is patched in the context module
    return (target_reference.fully_qualified_name(),)
