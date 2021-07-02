from __future__ import annotations

from typing import Type, TypeVar, Generic, Optional, Any

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import unflex

JSON_TYPES = (str, bool, int, float, type(None))


T = TypeVar("T")
U = TypeVar("U")


class FlexFactory(Generic[T]):

    def __init__(self, klass: Type[T], strip_extras: bool = True, keep_raw: Optional[str] = None) -> None:
        self.klass = klass
        self.strip_extras = strip_extras
        self.keep_raw = keep_raw

    def __call__(self, **dirty_kwargs: Any) -> T:
        # convert the keys casings to match the target class
        converted_arguments = unflex(self.klass.__init__, dirty_kwargs, strip_extra=self.strip_extras)

        # scan the annotations for custom types and convert them
        for arg_name, arg_type in find_annotations(self.klass).items():
            if arg_type not in JSON_TYPES:
                # convert the argument to the target class
                factory = FlexFactory(arg_type, strip_extras=self.strip_extras, keep_raw=self.keep_raw)
                converted_arguments[arg_name] = factory(**converted_arguments[arg_name])

        # with everything converted, create an instance of the class
        instance = self.klass(**converted_arguments)

        # keep raw data?
        if self.keep_raw and hasattr(instance, "__dict__"):
            # can't do that if slots-based
            instance.__dict__[self.keep_raw] = dirty_kwargs

        return instance
