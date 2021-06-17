import shlex
from typing import List

from coveo_testing.parametrize import parametrize

from coveo_systools.subprocess import _build_command


TOKEN_WITH_SPACES = "some/file with spaces.txt"


@parametrize("command", (["which", "git"], ["exec", "--option", "--target", TOKEN_WITH_SPACES]))
def test_build_command(command: List[str]) -> None:
    """By default (quoted=False) everything will be handled by Popen, later."""
    assert list(_build_command(*command, quoted=False)) == command


@parametrize(
    ("command", "expected"),
    (
        (["which git"], ["which", "git"]),
        (
            ["exec --option", f"--target {shlex.quote(TOKEN_WITH_SPACES)}"],
            ["exec", "--option", "--target", shlex.quote(TOKEN_WITH_SPACES)],
        ),
    ),
)
def test_build_command_quoted(command: List[str], expected: List[str]) -> None:
    """With quoted=True, additional splitting occurs."""
    assert list(_build_command(*command, quoted=True)) == expected


def test_build_command_quoted_user_error() -> None:
    """Demonstrates why you need to quote tokens if quoted=True."""
    unquoted_command = f"exec --option {TOKEN_WITH_SPACES}"
    assert (
        " ".join(_build_command("exec", f"--option {TOKEN_WITH_SPACES}", quoted=True))
        == unquoted_command
    )


def test_build_command_user_error() -> None:
    """Demonstrates why you can't combine tokens if quoted=False."""
    misplaced_quote = f"exec '--option {TOKEN_WITH_SPACES}'"
    command = _build_command("exec", f"--option {TOKEN_WITH_SPACES}", quoted=False)

    # shlex.join() gives us a (close enough for the test) Popen constructor behavior.
    assert shlex.join(command) == misplaced_quote
