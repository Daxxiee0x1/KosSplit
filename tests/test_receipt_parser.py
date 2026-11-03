from kossplit.receipt_parser import (
    ReceiptItem,
    items_from_text,
    items_to_text,
    parse_amount,
    parse_receipt,
    rows_from_boxes,
)

RESTAURANT = """
MIE GACOAN SETURAN
Jl. Seturan Raya No. 12
12/05/2025 19:42
Mie Hompimpa Lv 3      38.000
Mie Suit               30.000
Udang Rambutan         22.000
Es Teh 2 x 9.000       18.000
Subtotal              108.000
PB1 10%                10.800
Total                 118.800
Tunai                 150.000
Kembali                31.200
"""

MINIMARKET = """
INDOMARET KALIURANG
AQUA GALON 19L
1 x 21.000 21.000
SABUN CUCI PIRING
2 x 8.500 17.000
Indomie Goreng 5 x 3.100 15.500
HARGA JUAL 53.500
DISKON PROMO -5.000
TOTAL BELANJA 48.500
TUNAI 50.000
KEMBALIAN 1.500
"""

# Printers and OCR often add cents (,00), a trailing comma or dash, IDR, or a k shorthand.
DECIMAL_RECEIPT = """
WARUNG NUSANTARA
Nasi Goreng Spesial   IDR 48.000,00
Ayam Bakar            Rp35.000,-
Es Jeruk 2 x 9.000    18.000,
Kerupuk               5k
Subtotal              106.000,00
PB1 10%               10.600,00
Total                 IDR 116.600,00
Tunai                 150.000,00
Kembali               33.400,00
"""


def test_parse_amount_formats():
    assert parse_amount("25.000") == 25_000
    assert parse_amount("25,000") == 25_000
    assert parse_amount("Rp 25.000,00") == 25_000
    assert parse_amount("1.250.000") == 1_250_000
    assert parse_amount("-5.000") == 5_000
    assert parse_amount("48.000,00") == 48_000
    assert parse_amount("48k") == 48_000


def test_receipt_with_decimals_idr_and_k_shorthand():
    draft = parse_receipt(DECIMAL_RECEIPT)
    assert draft.merchant == "WARUNG NUSANTARA"
    assert [(item.name, item.price) for item in draft.items] == [
        ("Nasi Goreng Spesial", 48_000),
        ("Ayam Bakar", 35_000),
        ("Es Jeruk x2", 18_000),
        ("Kerupuk", 5_000),
    ]
    assert draft.subtotal == 106_000
    assert draft.tax_service == 10_600
    assert draft.total == 116_600
    assert draft.notes == []


def test_restaurant_receipt_with_tax():
    draft = parse_receipt(RESTAURANT)
    assert draft.merchant == "MIE GACOAN SETURAN"
    assert [item.price for item in draft.items] == [38_000, 30_000, 22_000, 18_000]
    assert draft.items[3].name == "Es Teh x2"
    assert draft.subtotal == 108_000
    assert draft.tax_service == 10_800
    assert draft.total == 118_800
    assert draft.bill_values() == (108_000, 10_800, 0)


def test_minimarket_receipt_with_quantity_lines_and_discount():
    draft = parse_receipt(MINIMARKET)
    assert [(item.name, item.price) for item in draft.items] == [
        ("AQUA GALON 19L", 21_000),
        ("SABUN CUCI PIRING x2", 17_000),
        ("Indomie Goreng x5", 15_500),
    ]
    assert draft.discount == 5_000
    assert draft.total == 48_500
    subtotal, fees, discount = draft.bill_values()
    assert subtotal + fees - discount == 48_500


def test_bill_values_absorbs_unexplained_gap():
    draft = parse_receipt("Nasi 20.000\nTeh 5.000\nTotal 27.500")
    assert draft.tax_service == 2_500
    assert draft.bill_values() == (25_000, 2_500, 0)


def test_rows_from_boxes_merges_columns():
    boxes = [
        ("Nasi goreng", 10, 100, 120, 120),
        ("Es jeruk", 10, 130, 90, 150),
        ("25.000", 300, 102, 360, 121),
        ("8.000", 305, 131, 360, 149),
    ]
    assert rows_from_boxes(boxes) == "Nasi goreng  25.000\nEs jeruk  8.000"


def test_item_text_round_trip():
    items = [ReceiptItem("Nasi", 20_000), ReceiptItem("Teh", 5_000)]
    assert items_from_text(items_to_text(items)) == items
