import functools
import re
from typing import Match, Iterable, Dict, Callable, Any, TypeVar, Mapping, Type, Final

import inflection

from .annotations import find_annotations


T = TypeVar("T")


# noinspection PyDefaultArgument
def snake_case(string: str, bad_casing: Iterable[str] = ()) -> str:
    """return the snake cased version of a string. bad casings may be specified: if the bad casing is found, the word
    is replaced with Titlecase:

        Without bad_casing:             SomeTimeOut_s -> some_time_out_s
        With ['TimeOut'] as bad_casing: SomeTimeOut_s -> some_timeout_s
    """

    # find groups of uppercase letters like: Some(URIs), (CDF)Node, (DPMs), (IDs)
    # alter the groups as such: Some(Uris), (CdfNo)ode, (Dpms), (Ids)
    # this will remove most ambiguities for inflection.underscore() to react correctly
    def _replace_caps_clusters(match: Match) -> str:
        sub: str = match.group()
        if len(sub) <= 3:  # DBs / DPM / ID / Id...
            return sub.title()
        boundary = -2 if sub[-1].isupper() else -1
        return sub[:boundary].title() + sub[boundary:]

    prepared = re.sub(
        pattern=re.compile(r"([A-Z]{2,}[a-z]?(?=$|[^a-z]))"),
        repl=_replace_caps_clusters,
        string=string,
    )

    # check if we can find any of the words and fix their casing
    for word in bad_casing:
        if word in prepared:
            prepared = prepared.replace(word, word.title())

    result = inflection.underscore(prepared)
    assert isinstance(result, str)  # mypy

    def _remove_digits_underscore(match: Match) -> str:
        sub: str = match.group()
        assert sub[-1] == "_"
        return sub[:-1]

    # inflection will add an underscore after numbers. we don't want that.
    result = re.sub(pattern=r"\d+_", repl=_remove_digits_underscore, string=result)
    return result


TRANSLATION_TABLE: Final = str.maketrans("", "", "_-. ")


class _FlexcaseDecorator:
    """Allow passing kwargs to a method without consideration for casing or underscores."""

    __slots__ = "strip_extra", "allowed_extras"

    def __init__(self, *, strip_extra: bool = True, allowed_extras: Iterable[str] = None) -> None:
        self.strip_extra = strip_extra
        self.allowed_extras = allowed_extras

    def __call__(self, fn: Callable[..., T]) -> Callable[..., T]:
        _aliases: Dict[str, str] = self.create_lookup(fn, self.allowed_extras)

        @functools.wraps(fn)
        def _wrapper(*args: Any, **kw: Any) -> Any:
            __tracebackhide__ = True
            return fn(*args, **self.unflex(_aliases, kw))

        return _wrapper

    def unflex(self, lookup: Mapping[str, str], kwargs: Mapping[str, Any]) -> Dict[str, Any]:
        """Return a copy of kwargs with the correct case."""
        clean = {}
        for key in kwargs:
            lookup_key = self._lookup_key(key)
            if lookup_key not in lookup:
                if self.strip_extra:
                    continue
                clean[key] = kwargs[key]  # don't touch this one, let it explode later
            else:
                clean[lookup[lookup_key]] = kwargs[key]

        return clean

    @classmethod
    def create_lookup(cls, fn: Callable, extras: Iterable[str] = None) -> Dict[str, str]:
        """Create a simple lookup of stripped underscore + lowercased -> Original bases on the function's annotation.
        Additional kwargs may be allowed to go through by using `extras`
        """
        return {
            cls._lookup_key(annotation): annotation
            for annotation in list(find_annotations(fn)) + list(extras or [])
            if annotation != "return"
        }

    @staticmethod
    def _lookup_key(key: str) -> str:
        """Return a normalized lookup key."""
        return key.translate(TRANSLATION_TABLE).lower()


def flexcase(
    fn: Callable[..., T], *, strip_extra: bool = True, allowed_extras: Iterable[str] = None
) -> Callable[..., T]:
    """Return fn wrapped in flexcase magic.

    Can be used as decorator over methods and functions: @flexcase
    Can be used as a one-time delegate: result = flexcase(obj.method)(**dirty_casings)
    """
    return _FlexcaseDecorator(strip_extra=strip_extra, allowed_extras=allowed_extras)(fn)


def unflex(
    fn: Callable, dirty_kwargs: Mapping[str, Any], strip_extra: bool = True
) -> Dict[str, Any]:
    """Opposite of flexcase; return a clean version of dirty_kwargs with correct case and extra kwargs stripped out."""
    flex: _FlexcaseDecorator = _FlexcaseDecorator(strip_extra=strip_extra)
    return flex.unflex(flex.create_lookup(fn), dirty_kwargs)


def flexfactory(cls: Type[T], *, strip_extra: bool = True, **dirty_kwargs: Any) -> T:
    """Syntactic sugar that maps kwargs to a class's constructor arguments and return an instance of it.
    E.g.:

    class ClassWithArgs:
        def __init__(self, arg1, arg2) -> None:
            ...

    return flexfactory(ClassWithArgs, {'Arg1': 10, 'ARG2': 20})
    """
    return cls(**unflex(cls.__init__, dirty_kwargs, strip_extra=strip_extra))  # type: ignore
