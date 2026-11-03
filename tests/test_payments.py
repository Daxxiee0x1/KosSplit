from kossplit.payments import (
    format_payment_info,
    normalize_phone,
    parse_payment_info,
    payment_reminder,
    whatsapp_url,
)


def test_detects_bank_and_account_number():
    target = parse_payment_info("BCA 123 456 7890 a.n. Ayu")
    assert target.provider.key == "bca"
    assert target.account_number == "1234567890"


def test_prefers_specific_provider():
    assert parse_payment_info("blu by BCA 001234567").provider.key == "blu"
    assert parse_payment_info("GoPay 0813-3333-4444").provider.key == "gopay"


def test_unknown_provider_keeps_number():
    target = parse_payment_info("Jago 1029384756")
    assert target.provider is None
    assert target.account_number == "1029384756"


def test_format_payment_info():
    assert format_payment_info("BCA mobile", "123-456", "Ayu") == "BCA mobile 123456 a.n. Ayu"


def test_whatsapp_link():
    assert normalize_phone("0812 1111 2222") == "6281211112222"
    message = payment_reminder("Bima", "Ayu", 42_500, parse_payment_info("BCA 1234567890"))
    assert "Rp42.500" in message
    assert whatsapp_url("0812", message).startswith("https://wa.me/62812?text=Halo%20Bima")
