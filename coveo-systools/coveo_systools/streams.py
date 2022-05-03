import re

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


def filter_ansi(stream: bytes) -> bytes:
    """Removes ANSI sequences from a stream."""
    return bytes(ANSI_ESCAPE.sub(b"", stream))
