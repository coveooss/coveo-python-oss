"""Adds much needed magic and features over the builtin subprocess machinery."""


import logging
import shlex
import subprocess
from os import PathLike

from typing import Union, Any, Optional, cast, List, Dict, Tuple, Iterable, Generator
from typing_extensions import Protocol, Final, Literal

from coveo_functools.dispatch import dispatch

from .streams import filter_ansi

log = logging.getLogger(__name__)


class DetailedCalledProcessError(subprocess.CalledProcessError):
    """
    The CalledProcessError from the subprocess module only shows the exit code, even though it holds valuable
    information such as the command line, stdout and stderr. This one includes a lot more information.

    The preferred way is to use the `raise from` syntax:
        try:
            subprocess.check_call(...)
        except CalledProcessError as exception:
            raise DetailedCalledProcessError(working_folder=working_folder) from exception

    But, it will also pickup the currently active exception handler if there is one. This is equivalent as above:
        try:
            subprocess.check_call(...)
        except CalledProcessError:
            raise DetailedCalledProcessError(working_folder=working_folder)

    To link an exception outside the handler, use the `raise from` syntax:
        while retries:
            try:
                return subprocess.check_output(...)
            except CalledProcessException as exception:
                last_error = exception
        if isinstance(last_error, CalledProcessError):
            raise DetailedCalledProcessError from last_error
    """

    __attributes_to_use_from_wrapped_exception: Final[Tuple[str, ...]] = (
        "stdout",
        "stderr",
        "returncode",
        "cmd",
    )
    __wrapped_exception: Optional[BaseException] = None

    def __init__(self, **metadata: Any) -> None:
        """
        Initializes a new DetailedCalledProcessError. Arbitrary metadata may be given to guide the user:
            raise DetailedCalledProcessError(working_folder=self.project_folder, user=self.user)
        """
        # note: self._wrapped_exception is not available until we leave __init__
        self.__metadata: Dict[str, Any] = metadata

    @property
    def returncode(self) -> int:  # type: ignore  # mypy seems confused for this one...
        return cast(int, getattr(self._wrapped_exception, "returncode", 1))

    @property
    def output(self) -> Optional[Union[str, bytes]]:
        return cast(Optional[Union[str, bytes]], getattr(self._wrapped_exception, "output", None))

    @property
    def stderr(self) -> Optional[Union[str, bytes]]:
        return cast(Optional[Union[str, bytes]], getattr(self._wrapped_exception, "stderr", None))

    @property
    def cmd(self) -> Union[Iterable[str], str]:
        """The cmd from the underlying exception."""
        return cast(Union[Iterable[str], str], getattr(self._wrapped_exception, "cmd", ""))

    def decode_stderr(self) -> str:
        if self.stderr:
            return self._decode(self.stderr)
        return ""

    def decode_output(self) -> str:
        if self.stdout:
            return self._decode(self.output)
        return ""

    # CalledProcessError defines a 'stdout' alias for 'output'; let's do the same.
    decode_stdout = decode_output

    def command_str(self) -> str:
        """The 'cmd' from the underlying exception, separated with spaces"""
        command = self.cmd
        if isinstance(command, str):
            return command
        return " ".join(command)

    @property
    def _wrapped_exception(self) -> BaseException:
        """This is the wrapped exception, which was either given to us (`raise from` -> __cause__) or assigned
        automatically by python when you `raise` from an exception handler (-> __context__)."""
        # unfortunately, cause and context are assigned after __init__, else we wouldn't need this property.
        if self.__wrapped_exception is None:
            exception = self.__cause__ or self.__context__

            if exception is None:
                log.error(
                    f"{type(self).__name__} is unable to obtain exception cause or context. Using placebo."
                )
                exception = subprocess.CalledProcessError(1, "placebo-assert-exception-is-not-none")

            self.__wrapped_exception = exception

        assert self.__wrapped_exception is not None  # mypy
        return self.__wrapped_exception

    @staticmethod
    def _decode(
        value: Union[bytes, str, None],
        *,
        decode_errors: Optional[Literal["ignore", "replace"]] = "ignore",
    ) -> Optional[str]:
        """Handles str/bytes/None conversion to simplify code + strips whitespace."""
        if value is None:
            return None
        return (value.decode(errors=decode_errors) if isinstance(value, bytes) else value).strip()

    def __str__(self) -> str:
        """The main show!"""
        errors: List[str] = [f"{self._wrapped_exception}\n"]

        # add user-defined metadata to the error message.
        errors.extend(f"{key}: {value}" for key, value in self.__metadata.items())

        if isinstance(self._wrapped_exception, subprocess.CalledProcessError):
            errors.extend(
                [
                    f"command: {self.command_str()}",
                    f"exit code: {self.returncode}",
                ]
            )

            if self.stdout:
                errors.append(f"\n--<stdout>--\n{self.decode_stdout()}\n--</stdout>--\n")
            if self.stderr:
                errors.append(f"\n--<stderr>--\n{self.decode_stderr()}\n--</stderr>--\n")

        return "\n".join(errors)


class _CallProtocol(Protocol):
    """Adds type-check to the check_output and check_call protocols."""

    def __call__(
        self, command: Iterable[str], shell: bool = False, cwd: str = None, **kwargs: Any
    ) -> Optional[Union[str, bytes]]:
        ...


def _build_command(*command: Any, quoted: bool) -> Generator[str, None, None]:
    """Build the command for Popen."""
    converted_command = (
        arg for arg in map(cast_command_line_argument_to_string, command) if arg and arg.strip()
    )
    yield from shlex.split(
        " ".join(converted_command), posix=False
    ) if quoted else converted_command


def check_run(
    *command: Any,
    working_directory: Union[PathLike, str] = ".",
    capture_output: bool = False,
    verbose: bool = False,
    quoted: bool = False,
    **kwargs: Any,
) -> Optional[str]:
    """
    Proxy for subprocess.check_run and subprocess.check_output.

    Additional features:
        - command line is a variable args (instead of a list)
        - automatic conversion of output to a stripped string (instead of raw bytes)
        - automatic conversion of Path, bytes and number variables in command line
        - automatic filtering of ansi codes from the output
        - enhanced DetailedCalledProcessError on error (a subclass of the typical CalledProcessError)

    quoted:
        - When False, an argument is automatically quoted if it has a space (Popen's behavior):
            Good: 'exec', '--option', '--also', 'this value' -> exec --option --also "this value"
            Bad:  'exec', '--option', '--also this value' -> exec --option "--also this value" (quotes are misplaced)

        - With True, the arguments will be split on spaces, unless you quoted them beforehand:
            Good: 'exec --option', '--also "this value"' -> exec --option --also "this value"
            Bad:  'exec', '--option', '--also', 'this value' -> exec --option --also this value (quotes are missing)

    With `quoted=True` you can combine arguments together in single strings; this often improves readability.
    However, you MUST quote the tokens that may contain a space. Example with black formatting:

        without quoted:

            check_run(
                [
                    "executable",
                    "--verbose",
                    "--target",
                    filename,
                    "--dry-run",
                    "--with-onions"
                ]
            )

        with quoted:

            import shlex
            check_run(
                [
                    "executable --verbose",
                    f"--target {shlex.quote(filename)}",
                    "--dry-run --with-onions"
                ],
                quoted=True,
            )
    """
    if verbose:
        print(f"input arguments: {command}")

    converted_command = tuple(_build_command(*command, quoted=quoted))
    command_for_display = " ".join(converted_command) if quoted else shlex.join(converted_command)

    if verbose:
        print(f"calling: {command_for_display}")

    fn = cast(_CallProtocol, subprocess.check_output if capture_output else subprocess.check_call)
    try:
        output = fn(converted_command, cwd=str(working_directory), **kwargs)
    except subprocess.CalledProcessError as exception:
        raise DetailedCalledProcessError(working_folder=working_directory) from exception

    if capture_output:
        encoding: Tuple[str, ...] = tuple()  # emptiness; encoding uses system/OS defaults
        if isinstance(output, str):
            encoding = ("utf-8",)  # py3 strings are always utf-8
            output = output.encode(*encoding)
        assert isinstance(output, bytes)  # mypy
        try:
            return filter_ansi(output).decode(*encoding).strip()
        except UnicodeDecodeError:
            log.warning("An error occurred decoding the output stream; retrying in safe mode.")
            return output.decode(errors="ignore").strip()

    return None


def check_call(
    *command: Any,
    working_directory: Union[PathLike, str] = ".",
    verbose: bool = False,
    quoted: bool = False,
    **kwargs: Any,
) -> Optional[str]:
    """Proxy for subprocess.check_call"""
    return check_run(
        *command, working_directory=working_directory, verbose=verbose, quoted=quoted, **kwargs
    )


def check_output(
    *command: Any,
    working_directory: Union[PathLike, str] = ".",
    verbose: bool = False,
    quoted: bool = False,
    **kwargs: Any,
) -> Optional[str]:
    """Proxy for subprocess.check_output"""
    return check_run(
        *command,
        working_directory=working_directory,
        capture_output=True,
        verbose=verbose,
        quoted=quoted,
        **kwargs,
    )


@dispatch()
def cast_command_line_argument_to_string(value: Any) -> str:
    raise ValueError(f"Unsupported type for command line argument: {type(value)}")


@cast_command_line_argument_to_string.register(bool)  # it falls back to int if not specified!
def cast_command_line_argument_from_bool(value: bool) -> str:
    raise ValueError(f"Unsupported type for command line argument: {type(value)}")


@cast_command_line_argument_to_string.register(str)
def cast_command_line_argument_from_string(value: str) -> str:
    return value.lstrip()


@cast_command_line_argument_to_string.register(int)
@cast_command_line_argument_to_string.register(float)
def cast_command_line_argument_from_number(value: Union[int, float]) -> str:
    return str(value)


@cast_command_line_argument_to_string.register(PathLike)  # PathLike is "runtime checkable"
def cast_command_line_argument_from_path(value: PathLike) -> str:
    return str(value)
