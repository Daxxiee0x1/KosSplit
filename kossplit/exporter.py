"""Excel and PDF reports with Indonesian labels and Rupiah formatting."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from importlib.util import find_spec
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .labels import KIND_LABELS, METHOD_LABELS, date_label, period_label
from .money import rupiah

Row = Mapping[str, object]

# Excel shows the thousands separator of the user's locale, so Indonesian Excel reads Rp100.000.
RUPIAH_FORMAT = '"Rp"#,##0;-"Rp"#,##0;"Rp"0'
DATE_FORMAT = "dd mmm yyyy"
HEADER_FILL = PatternFill("solid", fgColor="1B2638")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=16, color="1B2638")
MUTED_FONT = Font(italic=True, color="7A8699")

NIGHT = (27, 38, 56)
AZURE = (47, 124, 246)
MUTED = (110, 122, 140)
EMBER = (214, 69, 51)
MINT = (22, 140, 96)
STRIPE = (243, 246, 250)
RULE = (214, 221, 232)


def month_totals(transactions: Iterable[Row], periods: Iterable[str] = ()) -> list[dict]:
    """Count and sum income and expense per YYYY-MM, newest month first."""
    totals: dict[str, dict] = {}

    def bucket(period: str) -> dict:
        return totals.setdefault(
            period,
            {"period": period, "expense_count": 0, "income_count": 0, "expense": 0, "income": 0},
        )

    for period in periods:
        bucket(period)
    for row in transactions:
        item = bucket(str(row["transaction_date"])[:7])
        kind = str(row["kind"])
        item[kind] += int(row["amount"])
        item[f"{kind}_count"] += 1
    return sorted(totals.values(), key=lambda item: item["period"], reverse=True)


# Excel -----------------------------------------------------------------------


def _write_table(sheet, start_row: int, headers: list[str], rows: list[list], formats: dict[int, str]):
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(row=start_row, column=column, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    for offset, values in enumerate(rows, start=1):
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=start_row + offset, column=column, value=value)
            if column in formats:
                cell.number_format = formats[column]
    last_column = get_column_letter(len(headers))
    sheet.freeze_panes = sheet.cell(row=start_row + 1, column=1)
    sheet.auto_filter.ref = f"A{start_row}:{last_column}{start_row + max(1, len(rows))}"
    for column, header in enumerate(headers, start=1):
        values = [header, *(row[column - 1] for row in rows)]
        longest = max(len(rupiah(v)) if isinstance(v, int) else len(str(v)) for v in values)
        sheet.column_dimensions[get_column_letter(column)].width = min(48, max(12, longest + 3))


def export_excel(path: str | Path, bills: Iterable[Row], transactions: Iterable[Row], today: date | None = None) -> Path:
    destination = Path(path)
    today = today or date.today()
    bills, transactions = list(bills), list(transactions)
    workbook = Workbook()

    summary = workbook.active
    summary.title = "Ringkasan"
    summary["A1"] = "Laporan KosSplit"
    summary["A1"].font = TITLE_FONT
    summary["A2"] = f"Dibuat {date_label(today.isoformat())}"
    summary["A2"].font = MUTED_FONT
    months = month_totals(transactions, [today.strftime("%Y-%m")])
    _write_table(
        summary,
        4,
        ["Bulan", "Jumlah pengeluaran", "Total pengeluaran", "Jumlah pemasukan", "Total pemasukan", "Sisa"],
        [
            [
                period_label(item["period"]),
                item["expense_count"],
                item["expense"],
                item["income_count"],
                item["income"],
                item["income"] - item["expense"],
            ]
            for item in months
        ],
        {3: RUPIAH_FORMAT, 5: RUPIAH_FORMAT, 6: RUPIAH_FORMAT},
    )

    _write_table(
        workbook.create_sheet("Transaksi"),
        1,
        ["Tanggal", "Bulan", "Anggota", "Jenis", "Kategori", "Keterangan", "Nominal"],
        [
            [
                date.fromisoformat(str(row["transaction_date"])[:10]),
                period_label(str(row["transaction_date"])[:7]),
                row["member_name"],
                KIND_LABELS.get(str(row["kind"]), row["kind"]),
                row["category"],
                row["description"],
                int(row["amount"]),
            ]
            for row in transactions
        ],
        {1: DATE_FORMAT, 7: RUPIAH_FORMAT},
    )

    _write_table(
        workbook.create_sheet("Tagihan"),
        1,
        ["Tanggal", "Judul", "Dibayar oleh", "Metode", "Subtotal", "Pajak & biaya", "Diskon", "Total"],
        [
            [
                date.fromisoformat(str(row["bill_date"])[:10]),
                row["title"],
                row["payer_name"],
                METHOD_LABELS.get(str(row["method"]), row["method"]),
                int(row["subtotal"]),
                int(row["tax_service"]),
                int(row["discount"]),
                int(row["grand_total"]),
            ]
            for row in bills
        ],
        {1: DATE_FORMAT, 5: RUPIAH_FORMAT, 6: RUPIAH_FORMAT, 7: RUPIAH_FORMAT, 8: RUPIAH_FORMAT},
    )

    workbook.save(destination)
    return destination


# PDF -------------------------------------------------------------------------


def _roboto() -> tuple[Path, Path] | None:
    """Kivy ships Roboto; locate it without importing Kivy, which would parse argv."""
    spec = find_spec("kivy")
    if not spec or not spec.submodule_search_locations:
        return None
    folder = Path(list(spec.submodule_search_locations)[0]) / "data" / "fonts"
    regular, bold = folder / "Roboto-Regular.ttf", folder / "Roboto-Bold.ttf"
    return (regular, bold) if regular.is_file() and bold.is_file() else None


class _Report(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(True, margin=18)
        fonts = _roboto()
        self.has_unicode_font = fonts is not None
        if fonts:
            self.add_font("Roboto", "", str(fonts[0]))
            self.add_font("Roboto", "B", str(fonts[1]))
            self.report_font = "Roboto"
        else:
            self.report_font = "Helvetica"

    def text_safe(self, value: object) -> str:
        # Core PDF fonts only cover Latin-1; replace anything else instead of failing.
        text = str(value)
        return text if self.has_unicode_font else text.encode("latin-1", "replace").decode("latin-1")

    def footer(self):
        self.set_y(-12)
        self.set_font(self.report_font, size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"KosSplit  ·  halaman {self.page_no()} dari {{nb}}", align="C")

    def heading(self, text: str):
        self.ln(4)
        self.set_font(self.report_font, "B", 12)
        self.set_text_color(*NIGHT)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def note(self, text: str):
        self.set_font(self.report_font, size=10)
        self.set_text_color(*MUTED)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")

    def table_rows(self, headers, rows, widths, align, colors=None):
        self.set_font(self.report_font, size=9)
        self.set_text_color(*NIGHT)
        self.set_draw_color(*RULE)
        with self.table(
            col_widths=widths,
            text_align=align,
            borders_layout="HORIZONTAL_LINES",
            headings_style=FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=NIGHT),
            cell_fill_color=STRIPE,
            cell_fill_mode="ROWS",
            line_height=6.5,
            padding=(1.6, 2),
        ) as table:
            heading = table.row()
            for title in headers:
                heading.cell(title)
            for index, values in enumerate(rows):
                row = table.row()
                for column, value in enumerate(values):
                    color = colors[index] if colors and column == len(values) - 1 else None
                    style = FontFace(emphasis="BOLD", color=color) if color else None
                    row.cell(self.text_safe(value), style=style)


def export_pdf(
    path: str | Path,
    bills: Iterable[Row],
    transactions: Iterable[Row],
    period: str | None = None,
    today: date | None = None,
) -> Path:
    """One-month report: summary, every transaction, and every shared bill of that month."""
    destination = Path(path)
    today = today or date.today()
    period = period or today.strftime("%Y-%m")
    month_rows = [row for row in transactions if str(row["transaction_date"]).startswith(period)]
    month_bills = [row for row in bills if str(row["bill_date"]).startswith(period)]
    totals = month_totals(month_rows, [period])[0]
    balance = totals["income"] - totals["expense"]

    pdf = _Report()
    pdf.add_page()
    pdf.set_font(pdf.report_font, "B", 20)
    pdf.set_text_color(*NIGHT)
    pdf.cell(0, 10, "Laporan KosSplit", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.report_font, "B", 12)
    pdf.set_text_color(*AZURE)
    pdf.cell(0, 7, period_label(period), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.report_font, size=9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, f"Dibuat {date_label(today.isoformat())}", new_x="LMARGIN", new_y="NEXT")

    pdf.heading("Ringkasan")
    pdf.table_rows(
        ["Keterangan", "Jumlah catatan", "Total"],
        [
            ["Pemasukan", f"{totals['income_count']} pemasukan", rupiah(totals["income"])],
            ["Pengeluaran", f"{totals['expense_count']} pengeluaran", rupiah(totals["expense"])],
            ["Sisa arus kas", f"{len(month_rows)} catatan", rupiah(balance)],
        ],
        (2, 2, 1.6),
        ("LEFT", "LEFT", "RIGHT"),
        [MINT, EMBER, EMBER if balance < 0 else NIGHT],
    )

    pdf.heading("Transaksi bulan ini")
    if month_rows:
        pdf.table_rows(
            ["Tanggal", "Keterangan", "Anggota", "Kategori", "Nominal"],
            [
                [
                    date_label(str(row["transaction_date"])),
                    row["description"],
                    row["member_name"],
                    row["category"],
                    ("-" if row["kind"] == "expense" else "+") + rupiah(int(row["amount"])),
                ]
                for row in month_rows
            ],
            (1.5, 3, 1.5, 2, 1.7),
            ("LEFT", "LEFT", "LEFT", "LEFT", "RIGHT"),
            [EMBER if row["kind"] == "expense" else MINT for row in month_rows],
        )
    else:
        pdf.note("Belum ada transaksi di bulan ini.")

    pdf.heading("Tagihan patungan bulan ini")
    if month_bills:
        pdf.table_rows(
            ["Tanggal", "Judul", "Dibayar oleh", "Metode", "Total"],
            [
                [
                    date_label(str(row["bill_date"])),
                    row["title"],
                    row["payer_name"],
                    METHOD_LABELS.get(str(row["method"]), str(row["method"])),
                    rupiah(int(row["grand_total"])),
                ]
                for row in month_bills
            ],
            (1.5, 3, 1.7, 1.7, 1.7),
            ("LEFT", "LEFT", "LEFT", "LEFT", "RIGHT"),
        )
    else:
        pdf.note("Belum ada tagihan patungan di bulan ini.")

    pdf.output(str(destination))
    return destination
