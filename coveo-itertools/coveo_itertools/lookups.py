from typing import cast, Mapping, Any, TypeVar


T = TypeVar("T")

_NOT_SPECIFIED = cast(T, object())  # type: ignore


def dict_lookup(source: Mapping[Any, T], *keys: Any, default: T = _NOT_SPECIFIED) -> T:
    """
    Lookup *keys recursively in source.
    Raises KeyError on the first missing key, unless a default is specified.

    e.g.:
        example = {'nested': {'key': {'lookup': True}}}
        assert dict_lookup(example, 'nested', 'key', 'lookup') == True
    """
    if not keys:
        return cast(T, source)

    try:
        return dict_lookup(source[keys[0]], *keys[1:])  # type: ignore

    except KeyError:
        if default is _NOT_SPECIFIED:
            raise
        return default

    except (IndexError, TypeError):
        # can happen when non-dict types are found
        raise KeyError(keys)
