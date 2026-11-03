from decimal import Decimal

import pytest

from kossplit.calculator import (
    custom_amount_split,
    equal_split,
    itemized_split,
    percentage_split,
    simplify_debts,
)


def test_equal_split_never_loses_a_rupiah():
    result = equal_split(100_000, [1, 2, 3])
    assert result == {1: 33_334, 2: 33_333, 3: 33_333}
    assert sum(result.values()) == 100_000


def test_percentage_must_be_exactly_one_hundred():
    with pytest.raises(ValueError):
        percentage_split(50_000, {1: Decimal("30"), 2: Decimal("60")})


def test_custom_amount_must_match_total():
    assert custom_amount_split(30_000, {1: 10_000, 2: 20_000})[2] == 20_000
    with pytest.raises(ValueError):
        custom_amount_split(30_000, {1: 10_000, 2: 10_000})


def test_itemized_allocates_tax_and_discount_proportionally():
    result = itemized_split(
        [("Nasi", 20_000, [1]), ("Minum", 10_000, [2])],
        tax_service=3_000,
        discount=0,
    )
    assert result == {1: 22_000, 2: 11_000}


def test_debt_simplification_shortens_chain():
    transfers = simplify_debts({1: -25_000, 2: 0, 3: 25_000})
    assert transfers == [(1, 3, 25_000)]
