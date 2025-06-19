import logging
from _pytest.logging import LogCaptureFixture

from coveo_systools.streams import filter_ansi
from coveo_systools.subprocess import _process_output


def test_conflicting_character() -> None:
    """Legacy bug; this sequence was introduced in a pip upgrade (a progress bar!) and broke the decoder."""
    content = b"\xe2\x94\x81"
    assert filter_ansi(content) == content


def test_filter_ansi() -> None:
    """Strip out ansi codes from sequence."""
    colors = b"\x1b[33mhello\x1b[0m"
    assert filter_ansi(colors) == b"hello"


def test_string_with_ansi_codes() -> None:
    """Filter ANSI sequences from string input."""
    colored = "\x1b[32mSuccess\x1b[0m"
    assert filter_ansi(colored) == "Success"


def test_empty_string_and_bytes() -> None:
    """Handle empty inputs correctly."""
    assert filter_ansi("") == ""
    assert filter_ansi(b"") == b""


def test_complex_ansi_sequences() -> None:
    """Handle complex ANSI sequences with multiple codes."""
    text = "\x1b[1;31;42mBold Red on Green\x1b[0m"
    assert filter_ansi(text) == "Bold Red on Green"


def test_invalid_type_raises_error() -> None:
    """Ensure TypeError is raised for invalid input types."""
    try:
        filter_ansi([1, 2, 3])  # type: ignore
        assert False, "Should have raised TypeError"
    except TypeError:
        pass


def test_cursor_and_screen_controls() -> None:
    """Handle cursor movement and screen control sequences."""
    text = "Line1\x1b[1A\x1b[2KLine2"  # up one line and clear line
    assert filter_ansi(text) == "Line1Line2"


def test_mixed_string_contents() -> None:
    """Handle strings with mix of ANSI and non-ANSI content."""
    text = "Normal\x1b[31mRed\x1b[0mNormal\x1b[1mBold"
    assert filter_ansi(text) == "NormalRedNormalBold"


def test_process_output_string() -> None:
    """Process a simple string without ANSI codes."""
    result = _process_output("hello world")
    assert result == "hello world"


def test_process_output_bytes() -> None:
    """Process bytes input with proper UTF-8 encoding."""
    result = _process_output(b"hello world")
    assert result == "hello world"


def test_process_output_with_ansi() -> None:
    """Process string with ANSI codes with removal enabled."""
    result = _process_output("\x1b[32mhello\x1b[0m world", remove_ansi=True)
    assert result == "hello world"


def test_process_output_keep_ansi() -> None:
    """Process string with ANSI codes with removal disabled."""
    text = "\x1b[32mhello\x1b[0m world"
    result = _process_output(text, remove_ansi=False)
    assert result == text


def test_process_output_strip_whitespace() -> None:
    """Ensure whitespace is stripped from output."""
    result = _process_output("  hello world\n\t")
    assert result == "hello world"


def test_process_output_invalid_utf8(caplog: LogCaptureFixture) -> None:
    """Handle invalid UTF-8 bytes with fallback decoding."""
    with caplog.at_level(logging.WARNING):
        result = _process_output(b"hello \xff world")
        assert "retrying in safe mode" in caplog.text
        assert "hello \ufffd world" == result


def test_process_output_empty() -> None:
    """Process empty input correctly."""
    assert _process_output("") == ""
    assert _process_output(b"") == ""


def test_process_output_mixed_content() -> None:
    """Process content with mix of ANSI codes and whitespace."""
    text = "  \x1b[1mBold\x1b[0m \n\t\x1b[31mRed\x1b[0m  "
    result = _process_output(text, remove_ansi=True)
    assert result == "Bold \n\tRed"


def test_process_output_with_emojis() -> None:
    """Process string containing emojis."""
    text = "Hello 👋 World 🌎"
    result = _process_output(text)
    assert result == "Hello 👋 World 🌎"


def test_process_output_bytes_with_emojis() -> None:
    """Process bytes containing UTF-8 encoded emojis."""
    text = "Hello 👋 World 🌎".encode()
    result = _process_output(text)
    assert result == "Hello 👋 World 🌎"


def test_process_output_emojis_with_ansi() -> None:
    """Process string containing both emojis and ANSI codes."""
    text = "\x1b[32mHello\x1b[0m 👋 \x1b[1mWorld\x1b[0m 🌎"
    result = _process_output(text, remove_ansi=True)
    assert result == "Hello 👋 World 🌎"
