import importlib
import inspect
from dataclasses import dataclass
from http.client import HTTPResponse
from types import ModuleType
from typing import Any, Literal, Optional, Sequence, Tuple, Union, overload
from unittest.mock import Mock


class CannotFindSymbol(AttributeError):
    """Occurs when a symbol cannot be imported from a module."""


class DuplicateSymbol(CannotFindSymbol):
    """Occurs when a symbol occurs more than once within a module."""


@dataclass(frozen=True)
class _PythonReference:
    """A helper class around resolving and importing python symbols."""

    module_name: str
    symbol_name: Optional[str] = None
    attribute_name: Optional[str] = None  # may be nested, such as NestedClass.attribute

    @property
    def fully_qualified_name(self) -> str:
        """Returns the fully dotted name, such as `tests_testing.mock_module.inner.MockClass.inner_function`"""
        return ".".join(filter(bool, (self.module_name, self.symbol_name, self.attribute_name)))

    @property
    def attribute_name_sequence(self) -> Sequence[str]:
        """Returns the attribute name as a nested sequence"""
        if not self.attribute_name:
            return ()

        return self.attribute_name.split(".")

    @property
    def nested_attribute_sequence(self) -> Sequence[str]:
        """Returns the nested attributes, if any. Doesn't include the last attribute."""
        return self.attribute_name_sequence[:-1]

    @property
    def last_attribute_name(self) -> Optional[str]:
        """
        The last attribute name is the last attribute in the nested attributes of a symbol.
        Not all references have an attribute name.

        e.g.:
        - `attribute` in module.MyClass.NestedClass.attribute
        """
        if attributes := self.attribute_name_sequence:
            return attributes[-1]
        return None

    def import_module(self) -> ModuleType:
        """Import and return the module."""
        return importlib.import_module(self.module_name)

    def import_symbol(self) -> Any:
        """Import and return the symbol. For modules, the module is returned."""
        module = self.import_module()
        try:
            return getattr(module, self.symbol_name) if self.symbol_name else module
        except AttributeError as exception:
            raise CannotFindSymbol from exception

    def import_nested_symbol(self) -> Any:
        """
        Imports the symbol, walk any nested attributes and return the symbol holding the last attribute.
        If no nested attributes exist, the main symbol is returned.

        e.g.:
        - `DoubleNestedClass` in module.MyClass.NestedClass.DoubleNestedClass.attribute
        - `MyClass` in module.MyClass.attribute
        """
        symbol = self.import_symbol()
        for nested_attribute in self.nested_attribute_sequence:
            symbol = getattr(symbol, nested_attribute)
        return symbol

    def with_module(self, module: Union[str, ModuleType]) -> "_PythonReference":
        """Returns a new instance of _PythonReference that targets the same symbol in a different module."""
        return _PythonReference(
            module_name=module if isinstance(module, str) else module.__name__,
            symbol_name=self.symbol_name,
            attribute_name=self.attribute_name,
        )

    def with_symbol(self, symbol_name: str) -> "_PythonReference":
        """Returns a new instance of _PythonReference that targets a different symbol."""
        return _PythonReference(
            module_name=self.module_name,
            symbol_name=symbol_name,
            attribute_name=self.attribute_name,
        )

    def with_attribute(self, attribute_name: str) -> "_PythonReference":
        """Returns a new instance of _PythonReference that targets a different symbol."""
        return _PythonReference(
            module_name=self.module_name,
            symbol_name=self.symbol_name,
            attribute_name=attribute_name,
        )

    @classmethod
    def from_any(cls, obj: Any) -> "_PythonReference":
        """
        Returns a _PythonReference based on an object.
        If obj is a string, it will be imported as is; therefore, it has to be a fully qualified, importable symbol.
        """
        if isinstance(obj, str):
            return cls.from_any(importlib.import_module(obj))

        if inspect.ismodule(obj):
            return cls(module_name=obj.__name__)

        try:
            qualifiers = obj.__qualname__.split(".")
        except AttributeError as exception:
            if isinstance(obj, property):
                return cls.from_property(obj)
            raise NotImplementedError(f"New use case? {obj} cannot be resolved.") from exception

        return cls.from_qualifiers(obj.__module__, *qualifiers)

    @classmethod
    def from_property(cls, prop: property) -> "_PythonReference":
        """Returns a _PythonReference based on a property."""
        for fn in filter(bool, (prop.fget, prop.fset)):
            qualifiers = fn.__qualname__.split(".")

            if len(qualifiers) == 1:
                continue  # if the function is attached to a module, we can't find the owner

            fn_reference = cls.from_qualifiers(fn.__module__, *qualifiers)
            symbol = fn_reference.import_nested_symbol()

            # try a direct hit first
            if symbol.__dict__.get(fn_reference.last_attribute_name) is prop:
                return fn_reference

            # fish for identity
            for attribute_name, obj in symbol.__dict__.items():
                if obj is prop:
                    return fn_reference.with_attribute(attribute_name)

        raise CannotFindSymbol(f"Cannot find the owner of {prop} by inspecting its getter/setter.")

    @classmethod
    def from_qualifiers(cls, module_name: str, *qualifiers: str) -> "_PythonReference":
        """Return a _PythonReference based on the module name and qualifiers."""
        if not any(qualifiers):
            return cls(module_name=module_name)

        importable = qualifiers[0]

        if len(qualifiers) == 1:
            # this is a symbol defined at the module level
            return cls(module_name=module_name, symbol_name=importable, attribute_name=None)

        # this is an attribute on a symbol
        return cls(
            module_name=module_name, symbol_name=importable, attribute_name=".".join(qualifiers[1:])
        )


def _coerce(reference: _PythonReference, module: Union[ModuleType, str]) -> _PythonReference:
    """
    Find `reference` in `module` and return a _PythonReference that points to it.
    Will find renamed symbols such as `from this import that as thing`.
    """
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

        return new_reference.with_symbol(symbols_found[0])

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
# def ref(target: Any, *, context: Any, obj: Literal[True]) -> NoReturn: ...


def ref(
    target: Any, *, context: Optional[Any] = None, obj: bool = False
) -> Union[Tuple[str], Tuple[str, str]]:
    """
    Replaces `resolves_mock_target`. Named for brevity.

    Returns a tuple meant to be unpacked into the `mock.patch` or `mock.patch.object` functions in order to enable
    refactorable mocks.

    In order to target the module where the mock will be used, use the `context` argument. It can be either:
        - A module name as a string (e.g.: "coveo_testing.logging", but more importantly, __name__)
        - A symbol that belongs to the module to patch (i.e.: any function or class defined in that module)

    The "tl;dr" is to provide the thing to mock as the target, and the thing that is being tested as the context.
    For instance, pass the `HTTPResponse` class as the target and the `my_module.function_to_test` function
    as the context, so that `my_module.HTTPResponse` will be mocked.


    Note that the import style matters. To mock `HTTPResponse.get_headers`:

    - If `my_module` does `from httplib.client import HTTPResponse`:
        You must `*ref(HTTPResponse, context=something_defined_in_my_module)`

    - If `my_module` does `from httplib import client` or `import httplib`:
        You may `*ref(HTTPResponse)` without context, since a dot `.` is involved.


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

    source_reference = _PythonReference.from_any(target)

    if obj:
        # Not having an attribute name would be an error for `mock.patch.object` anyway.
        assert source_reference.attribute_name

        if self := getattr(target, "__self__", None):
            # how convenient, the instance is given to us!
            return self, source_reference.attribute_name
        else:
            raise Exception("You can patch this with patch(), no need for object.")

    context_reference = _PythonReference.from_any(context or target)
    target_reference = _coerce(source_reference, context_reference.module_name)

    if target_reference.attribute_name:
        # this can only be a method or property, which can be patched globally.
        return (target_reference.fully_qualified_name,)

    # everything else is patched in the context module
    return (target_reference.fully_qualified_name,)
