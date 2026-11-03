import pytest

from kossplit.money import (
    format_amount_input,
    format_thousands,
    parse_amount,
    reformat_typed_amount,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("48000", 48_000),
        ("48.000", 48_000),
        ("48,000", 48_000),
        ("Rp48.000", 48_000),
        ("Rp. 48.000", 48_000),
        ("IDR 48.000,00", 48_000),
        ("48.000,00", 48_000),
        ("48.000.00", 48_000),
        ("48.000,", 48_000),
        ("48.000,-", 48_000),
        ("48.000-", 48_000),
        ("48k", 48_000),
        ("48K", 48_000),
        ("48,5k", 48_500),
        ("48.5k", 48_500),
        ("1.250.000,00", 1_250_000),
        ("-5.000", 5_000),
        ("(5.000)", 5_000),
        ("", 0),
        ("  ", 0),
    ],
)
def test_parse_amount_indonesian_formats(text, expected):
    assert parse_amount(text) == expected


def test_parse_amount_rejects_words():
    with pytest.raises(ValueError):
        parse_amount("empat puluh ribu")


def test_format_thousands_uses_dots():
    assert format_thousands(0) == "0"
    assert format_thousands(950) == "950"
    assert format_thousands(1_500_000) == "1.500.000"


def test_format_amount_input_normalizes_any_format():
    assert format_amount_input("1500000") == "1.500.000"
    assert format_amount_input("IDR 48.000,00") == "48.000"
    assert format_amount_input("48k") == "48.000"
    assert format_amount_input("") == ""


def test_typing_digits_adds_dots_and_keeps_cursor_at_end():
    text, cursor = "", 0
    for digit in "1500000":
        text, cursor = reformat_typed_amount(text[:cursor] + digit + text[cursor:], cursor + 1)
    assert (text, cursor) == ("1.500.000", 9)


def test_typing_in_the_middle_keeps_cursor_beside_same_digit():
    # Cursor after "48" in "48.000", user types 5 -> raw "485.000" with cursor at 3.
    text, cursor = reformat_typed_amount("485.000", 3)
    assert text == "485.000"
    assert text[:cursor] == "485"
    # Raw "4855.000" re-dots to "4.855.000"; cursor stays right after the typed 5.
    text, cursor = reformat_typed_amount("4855.000", 4)
    assert text == "4.855.000"
    assert text[:cursor] == "4.855"


def test_backspace_removes_dot_when_number_shrinks():
    # "1.250.000" with the last 0 deleted -> raw "1.250.00", cursor at end.
    assert reformat_typed_amount("1.250.00", 8) == ("125.000", 7)


def test_reformat_clears_to_blank_and_strips_leading_zero():
    assert reformat_typed_amount("", 0) == ("", 0)
    assert reformat_typed_amount("05", 2) == ("5", 1)
    assert reformat_typed_amount("0", 1) == ("0", 1)
