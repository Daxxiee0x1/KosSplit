from datetime import date

from kossplit.database import Database


def test_bill_updates_balances(tmp_path):
    database = Database(tmp_path / "test.db")
    payer = database.add_member("Ayu", is_owner=True)
    friend = database.add_member("Bima")
    database.add_bill(
        title="Token listrik",
        payer_id=payer,
        method="equal",
        subtotal=100_000,
        tax_service=0,
        discount=0,
        shares={payer: 50_000, friend: 50_000},
    )
    assert database.balances() == {payer: 50_000, friend: -50_000}
    assert database.month_summary()["expense"] == 50_000
    database.add_settlement(friend, payer, 50_000)
    assert database.balances() == {payer: 0, friend: 0}
    database.close()


def test_transactions_are_separated_by_month_and_archived(tmp_path):
    database = Database(tmp_path / "periods.db")
    member = database.add_member("Ayu", is_owner=True)
    database.add_transaction(
        member, "expense", "Kos", "Sewa lama", 700_000, "2025-12-03"
    )
    database.add_transaction(
        member, "income", "Gaji", "Pemasukan baru", 1_000_000, "2026-01-02"
    )

    december = database.transactions_for_period("2025-12")
    january = database.transactions_for_period("2026-01")
    assert [row["description"] for row in december] == ["Sewa lama"]
    assert [row["description"] for row in january] == ["Pemasukan baru"]
    assert database.archived_periods(date(2026, 1, 15)) == ["2025-12"]
    assert database.month_summary("2025-12") == {"expense": 700_000, "income": 0}
    database.close()


def test_month_rollover_is_detected_without_deleting_records(tmp_path):
    database = Database(tmp_path / "rollover.db")
    member = database.add_member("Ayu")
    database.add_transaction(
        member, "expense", "Makan", "Catatan lama", 20_000, "2025-12-31"
    )

    assert database.activate_current_period(date(2025, 12, 31)) is False
    assert database.activate_current_period(date(2025, 12, 31)) is False
    assert database.activate_current_period(date(2026, 1, 1)) is True
    assert len(database.transactions_for_period("2025-12")) == 1
    assert database.transactions_for_period("2026-01") == []
    database.close()


def test_period_summaries_count_each_month(tmp_path):
    database = Database(tmp_path / "summaries.db")
    member = database.add_member("Ayu")
    database.add_transaction(member, "expense", "Makan", "Sarapan", 20_000, "2025-10-03")
    database.add_transaction(member, "expense", "Kos", "Galon", 15_000, "2025-10-09")
    database.add_transaction(member, "income", "Kiriman", "Kiriman", 1_000_000, "2025-10-01")

    summaries = database.period_summaries(date(2025, 11, 2))
    assert [item["period"] for item in summaries] == ["2025-11", "2025-10"]
    assert summaries[0] == {
        "period": "2025-11",
        "expense_count": 0,
        "income_count": 0,
        "expense": 0,
        "income": 0,
    }
    assert summaries[1] == {
        "period": "2025-10",
        "expense_count": 2,
        "income_count": 1,
        "expense": 35_000,
        "income": 1_000_000,
    }
    database.close()
