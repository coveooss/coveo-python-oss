from coveo_systools.streams import filter_ansi


def test_conflicting_character() -> None:
    """Legacy bug; this sequence was introduced in a pip upgrade (a progress bar!) and broke the decoder."""
    content = b"\xe2\x94\x81"
    assert filter_ansi(content) == content


def test_filter_ansi() -> None:
    """Strip out ansi codes from sequence."""
    colors = b"\x1b[33mhello\x1b[0m"
    assert filter_ansi(colors) == b"hello"
