from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .money import allocate_weighted


def equal_split(total: int, member_ids: list[int]) -> dict[int, int]:
    return allocate_weighted(total, {member_id: Decimal(1) for member_id in member_ids})


def percentage_split(total: int, percentages: dict[int, Decimal]) -> dict[int, int]:
    if sum(percentages.values(), Decimal(0)) != Decimal(100):
        raise ValueError("Total persentase harus tepat 100%")
    return allocate_weighted(total, percentages)


def custom_amount_split(total: int, amounts: dict[int, int]) -> dict[int, int]:
    if any(value < 0 for value in amounts.values()) or sum(amounts.values()) != total:
        raise ValueError("Jumlah nominal kustom harus sama dengan total tagihan")
    return dict(amounts)


def itemized_split(
    items: list[tuple[str, int, list[int]]],
    tax_service: int = 0,
    discount: int = 0,
) -> dict[int, int]:
    subtotals: dict[int, int] = defaultdict(int)
    for _name, price, members in items:
        if price < 0 or not members:
            raise ValueError("Setiap item harus memiliki harga dan anggota")
        portions = equal_split(price, members)
        for member_id, value in portions.items():
            subtotals[member_id] += value

    subtotal = sum(subtotals.values())
    grand_total = subtotal + tax_service - discount
    if grand_total < 0:
        raise ValueError("Diskon tidak boleh melebihi subtotal dan biaya")
    if not subtotals:
        raise ValueError("Tambahkan minimal satu item")
    return allocate_weighted(
        grand_total,
        {member_id: Decimal(value) for member_id, value in subtotals.items()},
    )


def simplify_debts(balances: dict[int, int]) -> list[tuple[int, int, int]]:
    """Return transfers as (debtor_id, creditor_id, amount)."""
    debtors = [[member, -value] for member, value in balances.items() if value < 0]
    creditors = [[member, value] for member, value in balances.items() if value > 0]
    debtors.sort(key=lambda row: row[1], reverse=True)
    creditors.sort(key=lambda row: row[1], reverse=True)
    transfers: list[tuple[int, int, int]] = []
    debtor_index = creditor_index = 0

    while debtor_index < len(debtors) and creditor_index < len(creditors):
        debtor, debt = debtors[debtor_index]
        creditor, credit = creditors[creditor_index]
        amount = min(debt, credit)
        if amount:
            transfers.append((debtor, creditor, amount))
        debtors[debtor_index][1] -= amount
        creditors[creditor_index][1] -= amount
        if debtors[debtor_index][1] == 0:
            debtor_index += 1
        if creditors[creditor_index][1] == 0:
            creditor_index += 1
    return transfers
