from __future__ import annotations

import inspect
from typing import (
    Type,
    TypeVar,
    Generic,
    Optional,
    Any,
    get_args,
    get_origin,
    Union,
    Dict,
    Callable,
)

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import unflex, flexcase
from coveo_functools.exceptions import InvalidUnion, PositionalArgumentsNotAllowed

_ = unflex, flexcase  # mark them as used (forward compatibility vs docs)


JSON_TYPES = (str, bool, int, float, type(None))
META_TYPES = (Union, Optional)


T = TypeVar("T")


class FlexFactory(Generic[T]):
    def __init__(
        self,
        __wrapped: Optional[Union[Type[T], Callable[..., T]]] = None,
        *,
        strip_extras: bool = True,
        keep_raw: Optional[str] = None
    ) -> None:
        # when used as a decorator, __wrapped will be None; it will be given and assigned in __call__ instead.
        self.__wrapped = __wrapped
        self.strip_extras = strip_extras
        self.keep_raw = keep_raw

    def __call__(self, __wrapped: Optional[Type] = None, **dirty_kwargs: Any) -> T:
        if __wrapped is not None:
            """
            The decorator pattern will lead us here.
            At this stage, python called us with just the class and expects a wrapper.
            We return ourselves; the current method will be called again with kwargs exclusively.
            """
            if self.__wrapped is not None or dirty_kwargs:
                # it's not possible to have both __wrapped and dirty_kwargs; unless the caller inserted a
                # positional argument in his call.
                # note: this may be the only thing that happens with "self"; would be nice to support methods too.
                raise PositionalArgumentsNotAllowed

            self.__wrapped = __wrapped
            return self  # type: ignore[return-value]

        if inspect.isclass(self.__wrapped):
            fn: Callable[..., T] = self.__wrapped.__init__  # type: ignore[misc]
        else:
            assert callable(self.__wrapped)
            fn = self.__wrapped

        # convert the keys casings to match the target class
        mapped_kwargs = unflex(fn, dirty_kwargs, strip_extra=self.strip_extras)
        converted_kwargs: Dict[str, Any] = {}

        # scan the annotations for custom types and convert them
        for arg_name, arg_type in find_annotations(fn).items():
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
        instance = self.__wrapped(**converted_kwargs)  # type: ignore[call-arg]

        # inject the raw payload if it wasn't already injected in the constructor:
        if self.keep_raw and not hasattr(instance, self.keep_raw):
            if hasattr(instance, "__dict__"):
                # if the raw data was explicitly given in kwargs, use that instead.
                instance.__dict__[self.keep_raw] = dirty_kwargs.get(self.keep_raw, dirty_kwargs)

        return instance
