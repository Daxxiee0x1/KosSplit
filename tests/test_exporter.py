from datetime import date

from openpyxl import load_workbook

from kossplit.database import Database
from kossplit.exporter import export_excel, export_pdf, month_totals
from kossplit.money import rupiah


def _sample(tmp_path):
    database = Database(tmp_path / "export.db")
    ayu = database.add_member("Ayu", is_owner=True)
    bima = database.add_member("Bima")
    database.add_transaction(ayu, "expense", "Makan & Minum", "Makan sushi", 100_000, "2025-11-02")
    database.add_transaction(ayu, "income", "Uang kiriman", "Kiriman", 1_500_000, "2025-11-01")
    database.add_transaction(ayu, "expense", "Kos", "Galon", 20_000, "2025-10-12")
    # The bill and its "Patungan" share are dated today, so they never touch 2025 totals.
    database.add_bill("Token listrik", ayu, "equal", 100_000, 0, 0, {ayu: 50_000, bima: 50_000})
    return database


def test_negative_rupiah_puts_sign_first():
    assert rupiah(-100_000) == "-Rp100.000"
    assert rupiah(1_500_000) == "Rp1.500.000"


def test_month_totals_counts_each_kind():
    rows = [
        {"transaction_date": "2026-11-02", "kind": "expense", "amount": 100_000},
        {"transaction_date": "2026-11-01", "kind": "income", "amount": 5_000},
    ]
    assert month_totals(rows, ["2026-12"]) == [
        {"period": "2026-12", "expense_count": 0, "income_count": 0, "expense": 0, "income": 0},
        {"period": "2026-11", "expense_count": 1, "income_count": 1, "expense": 100_000, "income": 5_000},
    ]


def test_excel_uses_indonesian_labels_and_numbers(tmp_path):
    database = _sample(tmp_path)
    path = export_excel(
        tmp_path / "r.xlsx", database.recent_bills(), database.all_transactions(), date(2025, 11, 2)
    )
    book = load_workbook(path)
    assert book.sheetnames == ["Ringkasan", "Transaksi", "Tagihan"]
    summary = {row[0]: row[1:] for row in book["Ringkasan"].iter_rows(min_row=5, values_only=True)}
    assert summary["November 2025"] == (1, 100_000, 1, 1_500_000, 1_400_000)
    assert summary["Oktober 2025"] == (1, 20_000, 0, 0, -20_000)
    transactions = list(book["Transaksi"].iter_rows(min_row=2, values_only=True))
    kinds = {row[5]: row[3] for row in transactions}
    assert kinds["Makan sushi"] == "Pengeluaran"
    assert kinds["Kiriman"] == "Pemasukan"
    assert book["Tagihan"]["D2"].value == "Bagi rata"
    assert book["Transaksi"]["G2"].number_format.startswith('"Rp"')
    database.close()


def test_pdf_is_written_with_and_without_records(tmp_path):
    database = _sample(tmp_path)
    full = export_pdf(
        tmp_path / "full.pdf",
        database.recent_bills(),
        database.all_transactions(),
        "2025-11",
        date(2025, 11, 2),
    )
    empty = export_pdf(tmp_path / "empty.pdf", [], [], "2026-12", date(2026, 12, 1))
    for path in (full, empty):
        assert path.read_bytes().startswith(b"%PDF")
    database.close()
