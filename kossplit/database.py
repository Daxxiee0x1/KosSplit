from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    payment_info TEXT NOT NULL DEFAULT '',
    monthly_budget INTEGER NOT NULL DEFAULT 0,
    is_owner INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    bill_date TEXT NOT NULL,
    payer_id INTEGER NOT NULL REFERENCES members(id),
    method TEXT NOT NULL,
    subtotal INTEGER NOT NULL,
    tax_service INTEGER NOT NULL DEFAULT 0,
    discount INTEGER NOT NULL DEFAULT 0,
    grand_total INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bill_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    member_id INTEGER NOT NULL REFERENCES members(id),
    amount INTEGER NOT NULL,
    settled INTEGER NOT NULL DEFAULT 0,
    UNIQUE(bill_id, member_id)
);
CREATE TABLE IF NOT EXISTS settlements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_member_id INTEGER NOT NULL REFERENCES members(id),
    to_member_id INTEGER NOT NULL REFERENCES members(id),
    amount INTEGER NOT NULL,
    settled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES members(id),
    kind TEXT NOT NULL CHECK(kind IN ('expense', 'income')),
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount INTEGER NOT NULL,
    transaction_date TEXT NOT NULL,
    source_bill_id INTEGER REFERENCES bills(id)
);
CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def members(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM members ORDER BY is_owner DESC, name COLLATE NOCASE"
        ).fetchall()

    def add_member(
        self,
        name: str,
        phone: str = "",
        payment_info: str = "",
        monthly_budget: int = 0,
        is_owner: bool = False,
    ) -> int:
        cursor = self.connection.execute(
            """INSERT INTO members(name, phone, payment_info, monthly_budget, is_owner)
               VALUES (?, ?, ?, ?, ?)""",
            (name.strip(), phone.strip(), payment_info.strip(), monthly_budget, int(is_owner)),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_transaction(
        self,
        member_id: int,
        kind: str,
        category: str,
        description: str,
        amount: int,
        transaction_date: str | None = None,
        source_bill_id: int | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """INSERT INTO transactions
               (member_id, kind, category, description, amount, transaction_date, source_bill_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                member_id,
                kind,
                category,
                description.strip(),
                amount,
                transaction_date or date.today().isoformat(),
                source_bill_id,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def activate_current_period(self, today: date | None = None) -> bool:
        """Persist the active calendar period and report an actual month rollover."""
        period = (today or date.today()).strftime("%Y-%m")
        row = self.connection.execute(
            "SELECT value FROM app_metadata WHERE key = 'active_period'"
        ).fetchone()
        previous = row["value"] if row else None
        if previous == period:
            return False
        self.connection.execute(
            """INSERT INTO app_metadata(key, value) VALUES ('active_period', ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (period,),
        )
        self.connection.commit()
        return previous is not None and previous != period

    def add_bill(
        self,
        title: str,
        payer_id: int,
        method: str,
        subtotal: int,
        tax_service: int,
        discount: int,
        shares: dict[int, int],
        notes: str = "",
    ) -> int:
        grand_total = subtotal + tax_service - discount
        if sum(shares.values()) != grand_total:
            raise ValueError("Total porsi tidak sama dengan total akhir")
        with self.connection:
            cursor = self.connection.execute(
                """INSERT INTO bills
                   (title, bill_date, payer_id, method, subtotal, tax_service,
                    discount, grand_total, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    title.strip(),
                    date.today().isoformat(),
                    payer_id,
                    method,
                    subtotal,
                    tax_service,
                    discount,
                    grand_total,
                    notes.strip(),
                ),
            )
            bill_id = int(cursor.lastrowid)
            for member_id, amount in shares.items():
                self.connection.execute(
                    "INSERT INTO bill_shares(bill_id, member_id, amount) VALUES (?, ?, ?)",
                    (bill_id, member_id, amount),
                )
                if member_id != payer_id:
                    self.connection.execute(
                        """INSERT INTO transactions
                           (member_id, kind, category, description, amount,
                            transaction_date, source_bill_id)
                           VALUES (?, 'expense', 'Patungan', ?, ?, ?, ?)""",
                        (
                            member_id,
                            title.strip(),
                            amount,
                            date.today().isoformat(),
                            bill_id,
                        ),
                    )
        return bill_id

    def recent_bills(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.connection.execute(
            """SELECT b.*, m.name AS payer_name
               FROM bills b JOIN members m ON m.id = b.payer_id
               ORDER BY b.bill_date DESC, b.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    def member(self, member_id: int) -> sqlite3.Row:
        return self.connection.execute(
            "SELECT * FROM members WHERE id = ?", (member_id,)
        ).fetchone()

    def add_settlement(self, from_member_id: int, to_member_id: int, amount: int) -> int:
        if amount <= 0 or from_member_id == to_member_id:
            raise ValueError("Pelunasan tidak valid")
        cursor = self.connection.execute(
            "INSERT INTO settlements(from_member_id, to_member_id, amount) VALUES (?, ?, ?)",
            (from_member_id, to_member_id, amount),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def transactions_for_period(self, period: str, limit: int = 1000) -> list[sqlite3.Row]:
        return self.connection.execute(
            """SELECT t.*, m.name AS member_name FROM transactions t
               JOIN members m ON m.id = t.member_id
               WHERE substr(t.transaction_date, 1, 7) = ?
               ORDER BY t.transaction_date DESC, t.id DESC LIMIT ?""",
            (period, limit),
        ).fetchall()

    def recent_transactions(self, limit: int = 30) -> list[sqlite3.Row]:
        return self.transactions_for_period(date.today().strftime("%Y-%m"), limit)

    def all_transactions(self, limit: int = 5000) -> list[sqlite3.Row]:
        return self.connection.execute(
            """SELECT t.*, m.name AS member_name FROM transactions t
               JOIN members m ON m.id = t.member_id
               ORDER BY t.transaction_date DESC, t.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    def archived_periods(self, today: date | None = None) -> list[str]:
        current = (today or date.today()).strftime("%Y-%m")
        rows = self.connection.execute(
            """SELECT DISTINCT substr(transaction_date, 1, 7) AS period
               FROM transactions
               WHERE length(transaction_date) >= 7
                 AND substr(transaction_date, 1, 7) < ?
               ORDER BY period DESC""",
            (current,),
        ).fetchall()
        return [str(row["period"]) for row in rows]

    def period_summaries(self, today: date | None = None) -> list[dict[str, int | str]]:
        """Counts and totals per calendar month, newest first; the running month is always present."""
        current = (today or date.today()).strftime("%Y-%m")
        rows = self.connection.execute(
            """SELECT substr(transaction_date, 1, 7) AS period,
                      SUM(kind = 'expense') AS expense_count,
                      SUM(kind = 'income') AS income_count,
                      COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount END), 0) AS expense,
                      COALESCE(SUM(CASE WHEN kind = 'income' THEN amount END), 0) AS income
               FROM transactions
               WHERE length(transaction_date) >= 7
               GROUP BY period"""
        ).fetchall()
        keys = ("expense_count", "income_count", "expense", "income")
        summaries = {
            str(row["period"]): {"period": str(row["period"]), **{key: int(row[key]) for key in keys}}
            for row in rows
        }
        summaries.setdefault(current, {"period": current, **{key: 0 for key in keys}})
        return sorted(summaries.values(), key=lambda item: str(item["period"]), reverse=True)

    def month_summary(self, month: str | None = None) -> dict[str, int]:
        month = month or date.today().strftime("%Y-%m")
        rows = self.connection.execute(
            """SELECT kind, COALESCE(SUM(amount), 0) total FROM transactions
               WHERE substr(transaction_date, 1, 7) = ? GROUP BY kind""",
            (month,),
        ).fetchall()
        values = {row["kind"]: int(row["total"]) for row in rows}
        return {"expense": values.get("expense", 0), "income": values.get("income", 0)}

    def category_summary(self, month: str | None = None) -> list[sqlite3.Row]:
        month = month or date.today().strftime("%Y-%m")
        return self.connection.execute(
            """SELECT category, SUM(amount) AS total FROM transactions
               WHERE kind = 'expense' AND substr(transaction_date, 1, 7) = ?
               GROUP BY category ORDER BY total DESC""",
            (month,),
        ).fetchall()

    def balances(self) -> dict[int, int]:
        balances = {int(row["id"]): 0 for row in self.members()}
        rows = self.connection.execute(
            """SELECT b.payer_id, s.member_id, s.amount
               FROM bill_shares s JOIN bills b ON b.id = s.bill_id
               WHERE s.settled = 0 AND s.member_id != b.payer_id"""
        ).fetchall()
        for row in rows:
            balances[int(row["payer_id"])] += int(row["amount"])
            balances[int(row["member_id"])] -= int(row["amount"])
        settlements = self.connection.execute(
            "SELECT from_member_id, to_member_id, amount FROM settlements"
        ).fetchall()
        for row in settlements:
            balances[int(row["from_member_id"])] += int(row["amount"])
            balances[int(row["to_member_id"])] -= int(row["amount"])
        return balances
