"""Turn OCR text from Indonesian receipts into an editable bill draft.

This module is pure Python so it can be unit tested on any computer. The
Android OCR bridge and the desktop fallback both feed text into it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .money import format_thousands, parse_amount

__all__ = [
    "ReceiptDraft",
    "ReceiptItem",
    "items_from_text",
    "items_to_text",
    "parse_amount",
    "parse_receipt",
    "rows_from_boxes",
]


@dataclass
class ReceiptItem:
    name: str
    price: int


@dataclass
class ReceiptDraft:
    merchant: str = ""
    items: list[ReceiptItem] = field(default_factory=list)
    subtotal: int = 0
    tax_service: int = 0
    discount: int = 0
    total: int = 0
    notes: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def items_total(self) -> int:
        return sum(item.price for item in self.items)

    @property
    def computed_total(self) -> int:
        return self.subtotal + self.tax_service - self.discount

    def bill_values(self) -> tuple[int, int, int]:
        """Return subtotal, fees, and discount that match the item list and receipt total.

        Itemized bills require the subtotal to equal the item prices. Any gap
        between that and the printed total is moved into fees or discount so
        the saved bill still matches the receipt to the rupiah.
        """
        subtotal = self.items_total
        tax_service = self.tax_service
        discount = self.discount
        if self.total:
            gap = self.total - (subtotal + tax_service - discount)
            if gap > 0:
                tax_service += gap
            elif gap < 0:
                discount += -gap
        return subtotal, tax_service, discount


# Prices at the end of a row: 38.000, Rp38.000, IDR 38.000,00, 38.000,-, 38.000, or 38k.
_AMOUNT_AT_END = re.compile(
    r"(?P<neg>[-(])?\s*(?:(?:rp\.?|idr)\s*)?"
    r"(?P<num>\d(?:[\d.,]*\d)?[kK]?(?:[.,]-?|-)?)\s*\)?\s*$",
    re.IGNORECASE,
)
_QTY_AT_END = re.compile(
    r"(?P<qty>\d+)\s*[xX×@]\s*(?:(?:rp\.?|idr)\s*)?[\d.,]+[kK]?\s*$", re.IGNORECASE
)
_DATE_OR_TIME = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}:\d{2}\b")

_SUBTOTAL = re.compile(r"\b(sub\s*-?\s*total|harga\s*jual|jumlah\s*harga)\b", re.IGNORECASE)
_DISCOUNT = re.compile(
    r"\b(disc(ount)?|diskon|potongan|promo|voucher|hemat|cashback)\b", re.IGNORECASE
)
_TAX = re.compile(
    r"\b(ppn|pajak|pb1|tax|service|servis|layanan|ongkir|ongkos|delivery|pengiriman|"
    r"biaya|packaging|kemasan|admin|platform)\b",
    re.IGNORECASE,
)
_TOTAL = re.compile(
    r"\b(grand\s*total|total(\s*(bayar|tagihan|belanja|harga|akhir))?|jumlah(\s*bayar)?|amount\s*due)\b",
    re.IGNORECASE,
)
_IGNORE = re.compile(
    r"\b(tunai|cash|kembali(an)?|change|debit|kredit|credit|kartu|card|qris|edc|npwp|telp|"
    r"tel|phone|kasir|cashier|struk|nota|trx|member|poin|point|terima\s*kasih|thank|bayar|"
    r"pembayaran|saldo|item|qty)\b",
    re.IGNORECASE,
)

MIN_PRICE = 100


def _has_letters(text: str, minimum: int = 2) -> bool:
    return len(re.findall(r"[A-Za-z]", text)) >= minimum


def _clean_name(text: str) -> str:
    name = re.sub(r"\s{2,}", " ", text).strip(" .:-*\t")
    return name


def rows_from_boxes(boxes: list[tuple[str, float, float, float, float]]) -> str:
    """Rebuild receipt rows from OCR line boxes.

    ML Kit often returns item names and prices as separate blocks. Each box is
    (text, left, top, right, bottom) in image coordinates. Boxes whose vertical
    centers are close are merged into one row, ordered from left to right.
    """
    ordered = sorted(boxes, key=lambda box: (box[2] + box[4]) / 2)
    rows: list[dict] = []
    for text, left, top, _right, bottom in ordered:
        center = (top + bottom) / 2
        height = max(1.0, bottom - top)
        if rows and abs(center - rows[-1]["center"]) <= max(height, rows[-1]["height"]) * 0.5:
            row = rows[-1]
            row["parts"].append((left, text))
            count = len(row["parts"])
            row["center"] = (row["center"] * (count - 1) + center) / count
            row["height"] = max(row["height"], height)
        else:
            rows.append({"center": center, "height": height, "parts": [(left, text)]})
    return "\n".join("  ".join(text for _, text in sorted(row["parts"])) for row in rows)


def parse_receipt(text: str) -> ReceiptDraft:
    draft = ReceiptDraft(raw_text=text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pending_name = ""
    tax_seen = discount_seen = False

    for index, line in enumerate(lines):
        match = _AMOUNT_AT_END.search(line)
        label = line[: match.start()] if match else line
        is_meta = bool(_DATE_OR_TIME.search(line))

        if not match or is_meta:
            if not draft.merchant and index < 4 and _has_letters(line, 3) and not is_meta:
                draft.merchant = _clean_name(line)
            elif _has_letters(line) and not is_meta and not _IGNORE.search(line):
                pending_name = _clean_name(line)
            else:
                pending_name = ""
            continue

        try:
            value = parse_amount(match.group("num"))
        except ValueError:
            pending_name = ""
            continue

        if _SUBTOTAL.search(label):
            draft.subtotal = value
        elif _DISCOUNT.search(label):
            draft.discount += value
            discount_seen = True
        elif _TAX.search(label):
            draft.tax_service += value
            tax_seen = True
        elif _TOTAL.search(label):
            draft.total = value
        elif _IGNORE.search(label):
            pass
        elif value >= MIN_PRICE:
            quantity = _QTY_AT_END.search(label)
            name_part = label[: quantity.start()] if quantity else label
            name = _clean_name(name_part)
            if not _has_letters(name) and pending_name:
                name = pending_name
            if _has_letters(name):
                if quantity and int(quantity.group("qty")) > 1:
                    name = f"{name} x{quantity.group('qty')}"
                draft.items.append(ReceiptItem(name=name, price=value))
        pending_name = ""

    if not draft.subtotal:
        draft.subtotal = draft.items_total
    if not draft.total:
        draft.total = draft.computed_total
    elif draft.total != draft.computed_total:
        gap = draft.total - draft.computed_total
        if gap > 0 and not tax_seen:
            draft.tax_service += gap
            draft.notes.append(f"Selisih Rp{format_thousands(gap)} dianggap biaya tambahan")
        elif gap < 0 and not discount_seen:
            draft.discount += -gap
            draft.notes.append(f"Selisih Rp{format_thousands(-gap)} dianggap diskon")
        else:
            draft.notes.append("Total struk berbeda dari hitungan. Periksa kembali angka.")
    if draft.items_total != draft.subtotal:
        draft.notes.append("Jumlah harga item belum sama dengan subtotal struk.")
    if not draft.items:
        draft.notes.append("Tidak ada item yang terbaca. Tambahkan item secara manual.")
    return draft


def items_to_text(items: list[ReceiptItem]) -> str:
    return "\n".join(f"{item.name}|{item.price}" for item in items)


def items_from_text(text: str) -> list[ReceiptItem]:
    items = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if "|" not in line:
            raise ValueError(f"Gunakan format nama|harga pada baris: {line}")
        name, price = line.rsplit("|", 1)
        if not name.strip():
            raise ValueError("Nama item tidak boleh kosong")
        items.append(ReceiptItem(name=name.strip(), price=parse_amount(price)))
    return items
