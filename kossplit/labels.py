"""Indonesian display labels shared by the screens and the exported reports."""

from __future__ import annotations

import re
from collections.abc import Iterable

MONTH_NAMES = (
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)

METHOD_LABELS = {
    "equal": "Bagi rata",
    "custom_amount": "Nominal kustom",
    "percentage": "Persentase",
    "itemized": "Per item",
}

KIND_LABELS = {"expense": "Pengeluaran", "income": "Pemasukan"}

CATEGORIES = (
    "Makan & Minum",
    "Kebutuhan Kos",
    "Transportasi",
    "Akademik",
    "Hiburan",
    "Lainnya",
)

# Common Indonesian store names and receipt words for each category.
CATEGORY_KEYWORDS = {
    "Makan & Minum": (
        "resto", "restoran", "rumah makan", "cafe", "kafe", "kopi", "coffee", "warung", "warteg",
        "bakso", "mie", "mi ayam", "nasi", "ayam", "geprek", "padang", "sate", "martabak", "burger",
        "pizza", "kfc", "mcd", "mcdonald", "starbucks", "janji jiwa", "kopi kenangan", "chatime",
        "mixue", "teh", "es", "jus", "roti", "bakery", "food", "makan", "minum", "gofood",
        "grabfood", "shopeefood", "sushi", "seblak", "soto", "gorengan", "snack",
    ),
    "Kebutuhan Kos": (
        "indomaret", "alfamart", "alfamidi", "superindo", "hypermart", "giant", "lotte mart",
        "minimarket", "toserba", "laundry", "gas", "elpiji", "lpg", "galon", "token", "listrik",
        "pln", "sabun", "deterjen", "rinso", "sampo", "shampoo", "pasta gigi", "odol", "tisu",
        "tissue", "pembersih", "sapu", "pel", "beras", "minyak goreng", "telur", "wifi", "indihome",
    ),
    "Transportasi": (
        "spbu", "pertamina", "shell", "bensin", "pertalite", "pertamax", "solar", "parkir",
        "gojek", "goride", "gocar", "grab", "grabbike", "grabcar", "ojek", "maxim", "krl",
        "commuter", "kai", "kereta", "tol", "bus", "transjakarta", "damri", "angkot",
    ),
    "Akademik": (
        "fotokopi", "fotocopy", "print", "printing", "gramedia", "buku", "atk", "alat tulis",
        "kertas", "pulpen", "pena", "pensil", "jilid", "kampus", "kuliah", "seminar",
    ),
    "Hiburan": (
        "bioskop", "cinema", "xxi", "cgv", "cinepolis", "netflix", "spotify", "youtube", "game",
        "karaoke", "inul vizta", "steam", "playstation", "timezone", "tiket konser",
    ),
}

_KEYWORD_PATTERNS = {
    category: re.compile(r"\b(" + "|".join(re.escape(word) for word in words) + r")\b")
    for category, words in CATEGORY_KEYWORDS.items()
}


def guess_category(merchant: str, item_names: Iterable[str] = ()) -> str:
    """Pick the most likely category for a scanned receipt, or 'Lainnya' when unsure.

    The store name counts three times as much as a single item, because "Indomaret"
    says more about the purchase than one snack on the list.
    """
    scores = dict.fromkeys(CATEGORY_KEYWORDS, 0)
    weighted = [(merchant, 3)] + [(name, 1) for name in item_names]
    for text, weight in weighted:
        lowered = text.lower()
        for category, pattern in _KEYWORD_PATTERNS.items():
            if pattern.search(lowered):
                scores[category] += weight
    best = max(scores, key=lambda category: scores[category])
    return best if scores[best] > 0 else "Lainnya"


def period_label(period: str) -> str:
    """'2026-11' -> 'November 2026'."""
    return f"{MONTH_NAMES[int(period[5:7]) - 1]} {period[:4]}"


def date_label(value: str) -> str:
    """'2026-11-02' -> '2 Nov 2026'."""
    return f"{int(value[8:10])} {MONTH_NAMES[int(value[5:7]) - 1][:3]} {value[:4]}"
