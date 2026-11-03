from __future__ import annotations

import re
from decimal import Decimal, ROUND_FLOOR


def rupiah(value: int) -> str:
    """Indonesian Rupiah with dot separators; negatives read '-Rp100.000'."""
    number = int(value)
    sign = "-" if number < 0 else ""
    return f"{sign}Rp{abs(number):,}".replace(",", ".")


def format_thousands(value: int) -> str:
    """Whole Rupiah with Indonesian thousand dots, without the Rp prefix: 1500000 -> 1.500.000."""
    return f"{int(value):,}".replace(",", ".")


_CURRENCY = re.compile(r"\b(?:rp|idr)\.?", re.IGNORECASE)
_SHORTHAND = re.compile(r"^(\d+(?:[.,]\d+)?)k$", re.IGNORECASE)


def parse_amount(text: str) -> int:
    """Parse Indonesian Rupiah amounts typed by users or read from receipts.

    Accepted examples, all whole Rupiah:
    48000, 48.000, 48,000, Rp 48.000, IDR 48.000,00, 48.000,-, 48.000, 48k, 48,5k.
    Two trailing decimals are cents and dropped; three trailing digits are thousands.
    Leading minus or parentheses are ignored because the receipt label decides the sign.
    """
    cleaned = _CURRENCY.sub("", str(text))
    cleaned = re.sub(r"[()\s]", "", cleaned).lstrip("-")
    cleaned = re.sub(r"[.,]?-$", "", cleaned)
    if not cleaned:
        return 0

    shorthand = _SHORTHAND.match(cleaned)
    if shorthand:
        value = Decimal(shorthand.group(1).replace(",", "."))
        return int((value * 1000).to_integral_value())

    cleaned = cleaned.rstrip(".,")
    if re.search(r"[.,]\d{2}$", cleaned):
        cleaned = cleaned[:-3]
    digits = re.sub(r"[.,]", "", cleaned)
    if not digits.isdigit():
        raise ValueError(f"Nominal tidak dikenali: {text}")
    return int(digits)


def format_amount_input(text: str) -> str:
    """Normalize free text into the dotted form shown in money fields; blank stays blank."""
    if not str(text).strip():
        return ""
    return format_thousands(parse_amount(text))


def reformat_typed_amount(text: str, cursor: int) -> tuple[str, int]:
    """Re-dot a money field after a keystroke and keep the cursor beside the same digit.

    The field only holds digits and thousand dots, so dots are dropped and rebuilt.
    Returns the new text and cursor index: ("1500000", 7) -> ("1.500.000", 9).
    """
    digits = re.sub(r"\D", "", text)
    formatted = format_thousands(int(digits)) if digits else ""
    cursor = max(0, min(cursor, len(text)))
    # Leading zeros disappear when re-dotted, so they no longer count toward the cursor.
    digits_left = len(re.sub(r"\D", "", text[:cursor]))
    digits_left -= min(digits_left, len(digits) - len(digits.lstrip("0") or "0"))
    index = 0
    while digits_left and index < len(formatted):
        if formatted[index].isdigit():
            digits_left -= 1
        index += 1
    return formatted, index


def allocate_weighted(total: int, weights: dict[int, Decimal]) -> dict[int, int]:
    """Allocate every rupiah deterministically with largest remainders."""
    if total < 0:
        raise ValueError("Total tidak boleh negatif")
    if not weights or any(weight < 0 for weight in weights.values()):
        raise ValueError("Bobot pembagian tidak valid")
    weight_total = sum(weights.values(), Decimal(0))
    if weight_total <= 0:
        raise ValueError("Total bobot harus lebih dari nol")

    exact = {
        key: Decimal(total) * weight / weight_total for key, weight in weights.items()
    }
    result = {
        key: int(value.to_integral_value(rounding=ROUND_FLOOR))
        for key, value in exact.items()
    }
    remainder = total - sum(result.values())
    order = sorted(
        exact,
        key=lambda key: (exact[key] - Decimal(result[key]), -key),
        reverse=True,
    )
    for key in order[:remainder]:
        result[key] += 1
    return result
