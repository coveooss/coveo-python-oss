from __future__ import annotations

from typing import Type, TypeVar, Generic, Optional, Any, get_args, get_origin, Union, Dict

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import unflex
from coveo_functools.exceptions import InvalidUnion

JSON_TYPES = (str, bool, int, float, type(None))
META_TYPES = (Union, Optional)


T = TypeVar("T")
U = TypeVar("U")


class FlexFactory(Generic[T]):
    def __init__(
        self, klass: Type[T], strip_extras: bool = True, keep_raw: Optional[str] = None
    ) -> None:
        self.klass = klass
        self.strip_extras = strip_extras
        self.keep_raw = keep_raw

    def __call__(self, **dirty_kwargs: Any) -> T:
        # convert the keys casings to match the target class
        mapped_kwargs = unflex(self.klass.__init__, dirty_kwargs, strip_extra=self.strip_extras)
        converted_kwargs: Dict[str, Any] = {}

        # scan the annotations for custom types and convert them
        for arg_name, arg_type in find_annotations(self.klass.__init__).items():
            if arg_name == self.keep_raw:
                # the constructor contains the raw attribute; inject the payload from here.
                # also, if the raw data was explicitly given in kwargs, use that instead.
                converted_kwargs[arg_name] = dirty_kwargs.get(arg_name, dirty_kwargs)
                continue

            if arg_name not in mapped_kwargs:
                continue  # this may be ok if the target class has a default value, will break if not

            if arg_type in JSON_TYPES:
                converted_kwargs[arg_name] = mapped_kwargs[arg_name]
                continue  # assume that builtin types are already converted

            meta_type = get_origin(arg_type)
            if meta_type in (Optional, Union):
                allowed_types = get_args(arg_type)
                if not all(_type in JSON_TYPES for _type in allowed_types):
                    raise InvalidUnion(meta_type)

                converted_kwargs[arg_name] = mapped_kwargs[arg_name]
                continue  # assume that builtin types are already converted

            # convert the argument to the target class
            factory = FlexFactory(arg_type, strip_extras=self.strip_extras, keep_raw=self.keep_raw)
            converted_kwargs[arg_name] = factory(**mapped_kwargs[arg_name])

        # with everything converted, create an instance of the class
        instance = self.klass(**converted_kwargs)  # type: ignore[call-arg]

        # inject the raw payload if it wasn't already injected in the constructor:
        if self.keep_raw and not hasattr(instance, self.keep_raw):
            if hasattr(instance, "__dict__"):
                # if the raw data was explicitly given in kwargs, use that instead.
                instance.__dict__[self.keep_raw] = dirty_kwargs.get(self.keep_raw, dirty_kwargs)

        return instance
