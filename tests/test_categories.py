from kossplit.labels import CATEGORIES, guess_category


def test_store_name_decides_category():
    assert guess_category("INDOMARET JL KALIURANG", ["Chitato", "Sabun Lifebuoy"]) == "Kebutuhan Kos"
    assert guess_category("Warung Bu Sri", []) == "Makan & Minum"
    assert guess_category("SPBU 44.552.01", ["Pertalite"]) == "Transportasi"
    assert guess_category("Fotokopi Barokah", ["Jilid skripsi"]) == "Akademik"
    assert guess_category("CGV Grand Indonesia", []) == "Hiburan"


def test_items_decide_when_store_is_unknown():
    assert guess_category("", ["Nasi goreng", "Es teh manis", "Kerupuk"]) == "Makan & Minum"


def test_unknown_receipt_falls_back_to_lainnya():
    assert guess_category("PT Sinar Jaya", ["Barang A"]) == "Lainnya"


def test_keywords_match_whole_words_only():
    # "teh" must not match inside "tehnik", and "gas" not inside "gasket".
    assert guess_category("Bengkel Tehnik", ["Gasket"]) == "Lainnya"


def test_guess_is_always_a_known_category():
    for merchant in ("Alfamart", "Kopi Kenangan", "Toko Abadi"):
        assert guess_category(merchant) in CATEGORIES
