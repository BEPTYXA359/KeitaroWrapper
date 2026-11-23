"""Тесты redistribute: сумма 100, все доли положительные, лишняя единица — первым элементам."""

import pytest

from app.services.shares import redistribute


@pytest.mark.parametrize("n", range(1, 11))
def test_sum_is_100_and_all_positive(n):
    shares = redistribute(n)

    assert len(shares) == n
    assert sum(shares) == 100
    assert all(share > 0 for share in shares)


def test_single_offer():
    assert redistribute(1) == [100]


def test_two_offers():
    assert redistribute(2) == [50, 50]


def test_three_offers():
    assert redistribute(3) == [34, 33, 33]


def test_four_offers():
    assert redistribute(4) == [25, 25, 25, 25]


def test_five_offers():
    assert redistribute(5) == [20, 20, 20, 20, 20]


def test_remainder_goes_to_first_elements():
    assert redistribute(7) == [15, 15, 14, 14, 14, 14, 14]


def test_zero_offers_raises():
    with pytest.raises(ValueError):
        redistribute(0)


# ----------------------------------------------------------------------
# Остаток после закреплённых долей
# ----------------------------------------------------------------------


def test_remainder_after_one_pinned_share():
    # закреплённый оффер держит 25%, двое остальных делят 75%; лишний процент — первому
    assert redistribute(2, 75) == [38, 37]


def test_remainder_after_pinned_share_divides_evenly():
    assert redistribute(3, 66) == [22, 22, 22]


def test_remainder_smaller_than_offer_count_gives_zeros():
    assert redistribute(3, 1) == [1, 0, 0]
    assert redistribute(3, 0) == [0, 0, 0]


@pytest.mark.parametrize("total", [0, 1, 25, 33, 66, 75, 99, 100])
@pytest.mark.parametrize("n", range(1, 11))
def test_remainder_sum_matches(n, total):
    assert sum(redistribute(n, total)) == total


def test_negative_remainder_raises():
    with pytest.raises(ValueError):
        redistribute(2, -1)
