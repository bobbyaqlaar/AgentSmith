"""Running balances, in integer minor units so nothing rounds."""

from __future__ import annotations


def balance(entries: list[int]) -> int:
    """The balance after every entry, credits positive and debits negative."""
    return sum(entries)


def overdrawn(entries: list[int]) -> bool:
    """Whether the running balance ever went below zero."""
    running = 0
    for entry in entries:
        running += entry
        if running < 0:
            return True
    return False
