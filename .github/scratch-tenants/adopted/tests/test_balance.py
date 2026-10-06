from ledger.balance import balance, overdrawn


def test_balance_sums_credits_and_debits() -> None:
    assert balance([500, -200, 50]) == 350


def test_overdrawn_is_about_the_running_balance_not_the_total() -> None:
    assert overdrawn([100, -200, 500])
    assert not overdrawn([100, -50, -50])
