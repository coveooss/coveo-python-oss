import importlib
import inspect
from dataclasses import dataclass
from textwrap import dedent
from types import ModuleType
from typing import Any, Literal, Optional, Sequence, Tuple, Union, overload
from unittest.mock import Mock


class RefException(Exception):
    """Base class for ref exceptions."""


class UsageError(RefException):
    """When ref detects usage errors."""


class NoQualifiedName(RefException, NotImplementedError):
    """When something has apparently no qualified name."""


class CannotImportModule(RefException, ImportError):
    """Occurs when an import fails."""


class CannotFindSymbol(RefException, AttributeError):
    """Occurs when a symbol cannot be imported from a module."""


class DuplicateSymbol(CannotFindSymbol):
    """Occurs when a symbol occurs more than once within a module."""


@dataclass(frozen=True)
class _PythonReference:
    """A helper class around resolving and importing python symbols."""

    module_name: str
    symbol_name: Optional[str] = None
    attributes: Optional[str] = None  # may have dots, such as NestedClass.attribute

    def __str__(self) -> str:
        return self.fully_qualified_name

    @property
    def fully_qualified_name(self) -> str:
        """Returns the fully dotted name, such as `tests_testing.mock_module.inner.MockClass.inner_function`"""
        return ".".join(filter(bool, (self.module_name, self.symbol_name, self.attributes)))

    @property
    def attributes_split(self) -> Sequence[str]:
        """Returns the attribute name as a nested sequence"""
        if not self.attributes:
            return ()

        return self.attributes.split(".")

    @property
    def nested_attributes(self) -> Sequence[str]:
        """Returns the nested attributes, if any. Doesn't include the last attribute."""
        return self.attributes_split[:-1]

    @property
    def last_attribute(self) -> Optional[str]:
        """
        The last attribute name is the last attribute in the nested attributes of a symbol.
        Not all references have an attribute name.

        e.g.:
        - `attribute` in module.MyClass.NestedClass.attribute
        """
        if not self.attributes:
            return None

        return self.attributes[-1]

    def import_module(self) -> ModuleType:
        """Import and return the module."""
        try:
            return importlib.import_module(self.module_name)
        except ImportError as exception:
            raise CannotImportModule(
                f"{__name__} tried to resolve {self} but was unable to import {self.module_name=}",
                name=self.module_name,
            ) from exception

    def import_symbol(self) -> Any:
        """Import and return the symbol. For modules, the module is returned."""
        module = self.import_module()

        try:
            return getattr(module, self.symbol_name) if self.symbol_name else module
        except AttributeError as exception:
            raise CannotFindSymbol(
                f"{__name__} tried to resolve {self}, but could not find {self.symbol_name=} in {self.module_name=}"
            ) from exception

    def import_nested_symbol(self) -> Any:
        """
        Imports the symbol, walk any nested attributes and return the symbol holding the last attribute.
        If no nested attributes exist, the main symbol is returned.

        e.g.:
        - `DoubleNestedClass` in module.MyClass.NestedClass.DoubleNestedClass.attribute
        - `MyClass` in module.MyClass.attribute
        """
        symbol = self.import_symbol()
        for nested_attribute in self.nested_attributes:
            try:
                symbol = getattr(symbol, nested_attribute)
            except AttributeError as exception:
                raise CannotFindSymbol(
                    f"{__name__} tried to resolve {self} but could not find {nested_attribute=} in {symbol=}"
                ) from exception
        return symbol

    def with_module(self, module: Union[str, ModuleType]) -> "_PythonReference":
        """Returns a new instance of _PythonReference that targets the same symbol in a different module."""
        return _PythonReference(
            module_name=module if isinstance(module, str) else module.__name__,
            symbol_name=self.symbol_name,
            attributes=self.attributes,
        )

    def with_symbol(self, symbol_name: str) -> "_PythonReference":
        """Returns a new instance of _PythonReference that targets a different symbol."""
        return _PythonReference(
            module_name=self.module_name,
            symbol_name=symbol_name,
            attributes=self.attributes,
        )

    def with_attributes(
        self, *attributes: str, keep_nested_attributes: bool = False
    ) -> "_PythonReference":
        """Returns a new instance of _PythonReference that targets a different attribute."""
        if keep_nested_attributes:
            attributes = *self.nested_attributes, *attributes

        return _PythonReference(
            module_name=self.module_name,
            symbol_name=self.symbol_name,
            attributes=".".join(attributes),
        )

    @classmethod
    def from_any(cls, obj: Any) -> "_PythonReference":
        """
        Returns a _PythonReference based on an object.

        If obj is a string, it will be imported as is; therefore, it has to be a fully qualified, importable symbol,
        and thus cannot contain attributes.
        """
        try:
            return cls._from_any(obj)
        except NoQualifiedName:
            if hasattr(obj, "__class__") and hasattr(obj.__class__, "__qualname__"):
                # this is most likely an instance; report the class.
                return cls.from_any(obj.__class__)
            raise

    @classmethod
    def _from_any(cls, obj: Any) -> "_PythonReference":
        if isinstance(obj, str):
            return cls.from_any(importlib.import_module(obj))

        if inspect.ismodule(obj):
            return cls(module_name=obj.__name__)

        if isinstance(obj, property):
            return cls.from_property(obj)

        try:
            qualifiers = obj.__qualname__.split(".")
        except AttributeError as exception:
            raise NoQualifiedName(f"New use case? {obj} cannot be resolved.") from exception

        return cls.from_qualifiers(obj.__module__, *qualifiers)

    @classmethod
    def from_property(cls, prop: property) -> "_PythonReference":
        """Returns a _PythonReference based on a property."""
        # Unlike functions, properties are naive and don't hold a link back to the class that holds them.
        # The black magic contained in this vial will inspect the setter and getter, which are assumed to be functions
        # that are defined on the same class as the property. We then fish that class to find the correct attribute that
        # contains our property.
        for fn in filter(bool, (prop.fget, prop.fset)):
            try:
                qualifiers = fn.__qualname__.split(".")
            except AttributeError:
                continue  # a potential edge case; the setters/getters could be a weird object.

            if len(qualifiers) == 1:
                continue  # if the function is attached to a module, we can't find the owner

            fn_reference = cls.from_qualifiers(fn.__module__, *qualifiers)
            symbol = fn_reference.import_nested_symbol()

            # try a direct hit first
            if symbol.__dict__.get(fn_reference.last_attribute) is prop:
                return fn_reference

            # fish for identity
            attributes_with_prop = tuple(
                attribute_name for attribute_name, obj in symbol.__dict__.items() if obj is prop
            )

            if len(attributes_with_prop) == 1:
                return fn_reference.with_attributes(
                    attributes_with_prop[0], keep_nested_attributes=True
                )

            if len(attributes_with_prop) > 1:
                raise DuplicateSymbol(
                    f"Ambiguous match: {prop} was found in multiple attributes of {symbol}: {attributes_with_prop=}"
                )

        raise CannotFindSymbol(f"Cannot find the owner of {prop} by inspecting its getter/setter.")

    @classmethod
    def from_qualifiers(cls, module_name: str, *qualifiers: str) -> "_PythonReference":
        """Return a _PythonReference based on the module name and qualifiers."""
        if any("<" in qualifier for qualifier in (module_name, *qualifiers)):
            # for instance, a lambda has a __qualname__ of `<lambda>` and generator expressions have `<genexpr>`.
            raise CannotFindSymbol(
                f"One of the qualifiers in {module_name} or {qualifiers} is a special object that cannot be resolved."
            )

        if not any(qualifiers):
            return cls(module_name=module_name)

        # it's possible that qualifiers[1:] contains nested modules; `importable` in this case is the symbol we will
        # be using `getattr` on later in order to "walk" the rest of the qualifiers.
        importable = qualifiers[0]

        if len(qualifiers) == 1:
            # this is a symbol defined at the module level
            return cls(module_name=module_name, symbol_name=importable, attributes=None)

        # this is an attribute on a symbol
        return cls(
            module_name=module_name, symbol_name=importable, attributes=".".join(qualifiers[1:])
        )


def _translate_reference_to_another_module(
    reference: _PythonReference, module: Union[ModuleType, str]
) -> _PythonReference:
    """
    Return a reference to the object pointed to by `reference`, in the context of how it was imported by `module`.

    For instance:
        - Reference A is defined in module B
        - Module C calls `from B import A as RenamedA`
        - Calling with (reference=A, module=C) will return a reference to "C.RenamedA"
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
                f"Duplicate symbols found for {symbol_to_find} in {module.__name__}: {symbols_found=}"
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
    """
    return f"{target.__module__}.{target.__name__}"


@overload
def ref(target: Any) -> Tuple[str]:
    ...


@overload
def ref(target: Any, *, context: Optional[Any]) -> Tuple[str]:
    ...


@overload
def ref(target: Any, *, obj: Literal[False]) -> Tuple[str]:
    ...


@overload
def ref(target: Any, *, context: Optional[Any], obj: Literal[False]) -> Tuple[str]:
    ...


@overload
def ref(target: Any, *, obj: Literal[True]) -> Tuple[Any, str]:
    ...


@overload
def ref(target: Any, *, context: Any, obj: Literal[True]) -> Tuple[Any, str]:
    ...


def ref(
    target: Any,
    *,
    context: Optional[Any] = None,
    obj: bool = False,
    _bypass_context_check: bool = False,
) -> Union[Tuple[str], Tuple[Any, str]]:
    """
    Replaces `resolves_mock_target`. Named for brevity.

    Returns a tuple meant to be unpacked into the `mock.patch` or `mock.patch.object` functions in order to enable
    refactorable mocks.

    The idea is to provide the thing to mock as the target, and sometimes, the thing that is being tested
    as the context. Refer to `coveo-testing`'s readme to better understand when a context is necessary.

    For example, pass the `HTTPResponse` class as the target and the `my_module.function_to_test` function
    as the context, so that `my_module.HTTPResponse` becomes mocked (and not httplib.client.HTTPResponse).

    The readme in this repository offers a lot of explanations, examples and recipes on how to mock things properly and
    when we don't need to provide a `context` argument.

    -- param: context
    In order to target the module where the mock will be used, use the `context` argument. It can be either:
        - A module name as a string (e.g.: "coveo_testing.logging", but more importantly, __name__)
        - A symbol that belongs to the module to patch (i.e.: any function or class defined in that module)
        - An instance, when patching special functions with `obj=True`

        e.g.: mock.patch(*ref(boto3, context=function_that_uses_boto3))

    -- param: obj
    In order to patch a single instance with `patch.object`, specify `obj=True`:

        e.g.: mock.patch.object(*ref(instance.fn, obj=True))
    """
    if isinstance(target, Mock) or isinstance(context, Mock):
        raise UsageError("Mocks cannot be resolved.")

    source_reference = _PythonReference.from_any(target)

    if obj:
        # Not having an attribute name would be an error for `mock.patch.object` anyway.
        if not source_reference.attributes:
            raise UsageError(
                f"Patching an object requires at least one attribute: {source_reference}"
            )

        if context is None:
            # normal functions link back to their instance through the __self__ dunder; such convenience!
            context = getattr(target, "__self__", None)

        if (context is None or isinstance(context, type)) and not _bypass_context_check:
            raise UsageError(
                dedent(
                    f"""
                Cannot resolve an instance for the context: this is important because {obj=} was specified.
                Applying this patch would most likely result in a global patch, contradicting the intent of {obj=}.
                
                If you are trying to patch a classmethod or staticmethod on a specific instance, you must provide that
                instance as the `context` argument.
                
                If the goal was to patch globally, remove the {obj=} argument, optionally provide a context 
                and use patch().
                
                If you believe this is a mistake, you can try to use `_bypass_context_check` and see if it works.
                If it does, please submit an issue with a quick test that reproduces the issue! <3
            """
                )
            )

        return context, source_reference.attributes

    context_reference = _PythonReference.from_any(context or target)
    target_reference = _translate_reference_to_another_module(
        source_reference, context_reference.module_name
    )

    return (target_reference.fully_qualified_name,)
