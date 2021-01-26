"""
CLI-feedback tool. Check the Styles class for the various styles offered.
Import the 'echo' shorthand for even more prettiness!

Summary:
    - ANSI support
    - Emoji support
    - Predefined styles for common cli feedback actions
    - Graceful failure reporting

Scroll to the bottom of this file for more info.
"""
import sys
from pathlib import Path
from pprint import pformat
from traceback import format_exception
from types import TracebackType
from typing import (
    Any,
    Generator,
    Dict,
    Optional,
    ClassVar,
    Tuple,
    Type,
    Iterable,
    Union,
    TYPE_CHECKING,
    Callable,
)

if TYPE_CHECKING:
    from typing_extensions import Final, Protocol
else:
    try:  # python 3.8
        from typing import Final, Protocol
    except ImportError:
        # use the extension module
        from typing_extensions import Final, Protocol

import click
from emoji import emojize

# these are the colors supported by click; some may vary based on global system settings:
_Black = "black"  # might be a gray
_Red = "red"
_Green = "green"
_Yellow = "yellow"  # might be an orange
_Blue = "blue"
_Magenta = "magenta"
_Cyan = "cyan"
_White = "white"  # might be light gray

_BrightBlack = "bright_black"
_BrightRed = "bright_red"
_BrightGreen = "bright_green"
_BrightYellow = "bright_yellow"
_BrightBlue = "bright_blue"
_BrightMagenta = "bright_magenta"
_BrightCyan = "bright_cyan"
_BrightWhite = "bright_white"

_Reset = "reset"  # reset the color code only


class _CallHook(Protocol):
    """Defines the interface we require from the call hook, for correctness."""

    def __call__(self, message: str, *, err: bool) -> None:
        ...


def _convert_to_strings(*objects: Any) -> Generator[str, None, None]:
    """Yield each object as a string. Some objects may yield multiple lines."""
    for obj in objects:
        if isinstance(obj, str):
            yield obj
        elif isinstance(obj, bytes):
            yield obj.decode("utf-8")
        elif isinstance(obj, Path):
            yield str(obj)
        elif isinstance(obj, BaseException):
            yield f"{type(obj).__name__}: {obj}"
        elif hasattr(obj, "__str__"):
            yield str(obj)
        else:
            yield pformat(
                obj
            )  # this is like json.dumps() but prettified and won't break on unknown types.


def _prettify_exception(
    value: BaseException = None, traceback: TracebackType = None
) -> Generator[Any, None, None]:
    """Yields pretty lines detailing an exception."""
    if not value or traceback:
        _, _val, _tb = sys.exc_info()
        value = value or _val
        traceback = traceback or _tb

    if not value and traceback:
        echo.error("No exception context to prettify.")
        return

    if isinstance(value, ExitWithFailure):
        # rewind to the cause for the header
        yield echo.error.prettify(value.__cause__, pad_after=False, emoji="exclamation")

        if value.failures is not None:
            yield from map(echo.error_details.copy(item=True).prettify, value.failures)

        if value.suggestions is not None:
            suggestions = list(value.suggestions)
            if len(suggestions) > 1:
                yield echo.suggest.prettify(
                    "The following hints may help diagnose the issue:", pad_after=False
                )
                yield from map(echo.normal.copy(item=True).prettify, suggestions)
            elif suggestions:
                yield echo.suggest.prettify(suggestions[0])
    else:
        yield echo.error.prettify("".join(format_exception(type(value), value, traceback)))
        yield echo.suggest.prettify(
            "This is an unhandled exception; report it if you can't fix it! !!stuck_out_tongue_winking_eye!!",
            emoji="bug",
        )

    yield ""


def _pretty_excepthook(
    type_: Type[BaseException], value: BaseException, traceback: TracebackType
) -> None:
    """The actual function that replaces sys.excepthook."""
    # restore the original hook so not to paint ourselves in a corner
    sys.excepthook = sys.__excepthook__
    for line in _prettify_exception(value, traceback):
        echo.passthrough(line)
    exit(getattr(value, "exit_code", 1))


def install_pretty_exception_hook() -> None:
    """Bootstraps the exception hook if necessary."""
    if sys.excepthook is _pretty_excepthook:
        return
    sys.excepthook = _pretty_excepthook


class ExitWithFailure(Exception):
    """
    CLI often requires displaying failures in a graceful way. This module offers a way to differentiate
    controlled errors from unhandled exceptions.

    First, run the bootstrap function:

        from ... import setup_pretty_excepthook
        setup_pretty_excepthook()  # but don't do this at module level

    Then, anywhere in your program, raise an ExitWithFailure from your exception. You can provide optional details and
    resolution steps:

        raise ExitWithFailure(failures=files, suggestions='run this: ...') from MyCustomException('you messed up!')

    Would display something like this:

        > MyCustomException: you messed up!
        >  - details[0]
        >  - details[1]
        >
        > Tip: run this: ...

    Anything else is considered unhandled and will show e.g.: a stacktrace and invite the user to file a bug.
    """

    def __init__(
        self,
        *,
        failures: Union[Iterable, str] = None,
        suggestions: Union[Iterable, str] = None,
        exit_code: int = 1,
    ) -> None:
        """
        Each individual object will be formatted as a bullet point.

        Parameters:
            failures: objects to help diagnose the failure
            suggestions: objects containing suggestions that may fix the problem
        """
        if isinstance(failures, str):
            failures = [failures]
        if isinstance(suggestions, str):
            suggestions = [suggestions]

        self.failures = failures
        self.suggestions = suggestions
        self.exit_code = exit_code

    def __str__(self) -> str:
        return "\n".join(_prettify_exception(self, self.__traceback__))


class Pretty:
    """Kinda like pretty-print, but over the top."""

    _delimiters: ClassVar[Tuple[str, str]] = ("!!", "!!")
    _emojize: ClassVar[bool] = True
    _item: ClassVar[str] = b"\xce\x87".decode("utf-8")  # a round, centered dot
    _safe_encode: ClassVar[bool] = False

    def __init__(
        self,
        *,
        call_hook: _CallHook = click.echo,
        emoji: str = None,
        pad_before: bool = False,
        pad_after: bool = False,
        item: bool = False,
        err: bool = False,
        default: str = None,
        **click_style_kw: Any,
    ) -> None:
        """Arguments specified here set defaults, but you can always override any of them on the spot.

        parameters:
            call_hook: the hook we use to print to the console.
            emoji: prepend the message with this emoji.
            pad_before: feed a \n before the message
            pad_after: feed an additional \n after the message
            item: use the item style (each line is indented + small bullet)
            err: print to stderr instead of stdin
            **kw: any additional keyword will be fed to click.style() (i.e.: ansi)

        emojis:
            A limited set of emojis is supported through the !!emoji_name!! syntax.
            The !! delimiters were chosen over standard colons because we display paths often.

            The source with the list of aliases is located here:
                https://github.com/carpedm20/emoji/blob/master/emoji/unicode_codes.py

            Known issue: the token must be surrounded by spaces else it won't work.
        """
        # dev note: make sure all the argument vs attribute names match up:
        # - so that copy() can remain simple and generic
        # - so we can use a dataclass later on
        self.emoji: Final[Optional[str]] = emoji
        self.pad_before: Final[bool] = pad_before
        self.pad_after: Final[bool] = pad_after
        self.item: Final[bool] = item
        self.err: Final[bool] = err
        self.call_hook: Final[_CallHook] = call_hook
        self.click_style_kw: Final[Dict[str, Any]] = click_style_kw
        self.default: Final[Optional[str]] = default

    def __call__(self, *messages: Any, **kw: Any) -> None:
        """prettify the messages and call `call_hook` with it."""
        if kw:
            self.copy(**kw)(*messages)  # delegate to a temporary instance
        else:
            try:
                self.call_hook(self.prettify(*messages), err=self.err)
            except UnicodeEncodeError:
                self.set_safe_encode()
                self.call_hook(self.prettify(*messages), err=self.err)

    @classmethod
    def set_safe_encode(cls, value: bool = True) -> None:
        """This is called automatically when encountering encoding issues on "some" system(s) *cough*"""
        cls._safe_encode = value

    def prettify(self, *messages: Any, **kw: Any) -> str:
        """
        Prettify the objects in messages:
        - Concatenate them as strings
        - Apply formatting config
        - Interpolate emojis
        - Return it
        """
        if kw:
            # delegate to temporary copy of self
            return self.copy(**kw).prettify(*messages)

        if not messages and self.default:
            messages = (self.default,)

        message = "".join(_convert_to_strings(*messages))

        if self.item:
            message = f" {self._item} {message}"
        if self.emoji and not self.item:
            message = f"{self._delimiters[0]}{self.emoji}{self._delimiters[1]} {message}"
        if self.pad_before:
            message = "\n" + message
        if self.pad_after:
            message += "\n"
        if self._delimiters[0] in message:
            message = emojize(message, use_aliases=True, delimiters=self._delimiters)

        if self._safe_encode:
            # remove any character that doesn't match stdout's encoding.
            message = message.encode(sys.stdout.encoding, errors="ignore").decode()

        return click.style(message, **self.click_style_kw)

    def copy(self, **kw: Any) -> "Pretty":
        """Creates a new instance like this one; new defaults may be specified."""
        merged_kw = self.__dict__.copy()
        merged_kw.update(merged_kw.pop("click_style_kw"))
        merged_kw.update(kw)
        return Pretty(**merged_kw)


class Styles:
    """
    Opinionated style guide for CLI messaging.

    Usage:
        from ... import echo

        echo.step("Launching some process...")
        echo.normal("Preparing work...")
        for work in things_to_do():
            echo.noise(work, item=True)
        echo.success("Alright, we're all done!")

    - You can always override any keyword per call.
    - You can always provide multiple messages (they will be concatenated with ''.join())
    - Use it like "msg = echo.noise.prettify(*messages, **kw)" to format a string beforehand.
        (Display it with echo.passthrough(msg))
    """

    # header-like; use it to headline each major step of the script
    step: Pretty = Pretty(fg=_BrightCyan, pad_before=True, pad_after=True)

    # header for outcomes (changed files, new resources, etc)
    outcome: Pretty = Pretty(fg=_Yellow, dim=True, bold=True, emoji="mega")

    # normal and noise are self-explanatory
    normal: Pretty = Pretty(fg=_White, dim=True, bold=True)
    noise: Pretty = Pretty(fg=_White, dim=True)

    # suggest uses a in-your-face style to catch attention, like how to resolve a problem
    suggest: Pretty = Pretty(fg=_Yellow, emoji="robot_face", pad_before=True, pad_after=True)

    # warnings informs the user about less-than-ideal situation that the code had to deal with.
    # a warning follow by a suggest is a great way to
    warning: Pretty = Pretty(fg=_Yellow, emoji="warning", pad_before=True, pad_after=True)

    # success and error are header-like and should be used sparingly
    # error and error_details will end up in stderr
    success: Pretty = Pretty(
        fg=_Green, emoji="heavy_check_mark", pad_before=True, pad_after=True, default="Success!"
    )
    error: Pretty = Pretty(fg=_Red, err=True, emoji="collision", pad_before=True, pad_after=True)
    error_details: Pretty = Pretty(fg=_Red, err=True, dim=True)

    # passthrough can be used to skip (or retain) formatting.
    passthrough: Pretty = Pretty()


# shortcut enables enhanced prettiness :sparkles:
echo = Styles
