import re

# 7-bit and 8-bit C1 ANSI sequences  (note: this is a bytes regex, not str)
# We use this to filter out ANSI codes from console outputs
# Source: https://stackoverflow.com/a/14693789/1741414
ANSI_ESCAPE_8BIT = re.compile(
    br"""
    (?: # either 7-bit C1, two bytes, ESC Fe (omitting CSI)
        \x1B
        [@-Z\\-_]
    |   # or a single 8-bit byte Fe (omitting CSI)
        [\x80-\x9A\x9C-\x9F]
    |   # or CSI + control codes
        (?: # 7-bit CSI, ESC [ 
            \x1B\[
        |   # 8-bit CSI, 9B
            \x9B
        )
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
""",
    re.VERBOSE,
)


def filter_ansi(stream: bytes) -> bytes:
    """Removes ANSI sequences from a stream."""
    return bytes(ANSI_ESCAPE_8BIT.sub(b"", stream))
