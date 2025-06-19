import re
from typing import TypeVar

# 7-bit and 8-bit C1 ANSI sequences  (note: this is a bytes regex, not str)
# We use this to filter out ANSI codes from console outputs
# Source: https://stackoverflow.com/a/14693789/1741414

# Update: Originally we used the regex with the 8-bit codes, but a pip upgrade
# introduced the character ━ (\xe2\x94\x81) to the stream. The `\xe2` was removed
# by one of the 8bit regex sequences.

# Since the goal is to remove colors and control codes, the simpler regex works just as well.

ANSI_ESCAPE = re.compile(
    rb"""
        \x1B  # ESC
        (?:   # 7-bit C1 Fe (except CSI)
            [@-Z\\-_]
        |     # or [ for CSI, followed by a control sequence
            \[
            [0-?]*  # Parameter bytes
            [ -/]*  # Intermediate bytes
            [@-~]   # Final byte
        )
""",
    re.VERBOSE,
)

# Convert the bytes pattern to a string pattern
ANSI_ESCAPE_STR = re.compile(ANSI_ESCAPE.pattern.decode(), re.VERBOSE)

T = TypeVar("T", str, bytes)


def filter_ansi(stream: T) -> T:
    """Removes ANSI sequences from a stream."""
    if isinstance(stream, str):
        return _filter_ansi_str(stream)
    elif isinstance(stream, bytes):
        return _filter_ansi_bytes(stream)
    else:
        raise TypeError("stream must be of type str or bytes")


def _filter_ansi_bytes(stream: bytes) -> bytes:
    """Removes ANSI sequences from a bytes stream."""
    return bytes(ANSI_ESCAPE.sub(b"", stream))


def _filter_ansi_str(string: str) -> str:
    """Removes ANSI sequences from a string."""
    return ANSI_ESCAPE_STR.sub("", string)
