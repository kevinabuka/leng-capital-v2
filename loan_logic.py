# loan_logic.py
from __future__ import annotations

def amount_due(P: float, weeks_elapsed: int) -> float:
    """
    Compute amount due on a loan.

    Rules (per Kevin's design):
    - Weekly interest: 10% compounded weekly on principal.
    - Late penalty: +2.5% of principal for each additional unpaid week beyond week 1.
    - Processing fee handled as a separate cash inflow at origination (db layer).
    - Transaction charge handled as a separate cash outflow at origination (db layer).
    """
    if weeks_elapsed <= 0:
        return float(P)

    # 10% interest per week, compounded
    base_due = P * ((1 + 0.10) ** weeks_elapsed)

    # Incremental penalty 2.5% * principal for each week AFTER the first
    penalty = 0.0
    if weeks_elapsed > 1:
        penalty = P * 0.025 * (weeks_elapsed - 1)

    return float(base_due + penalty)


def status_at(P: float, weeks_elapsed: int) -> str:
    """
    Very simple status helper for UI badges.
    """
    if weeks_elapsed <= 0:
        return "Current"
    if weeks_elapsed <= 1:
        return "Due soon"
    if weeks_elapsed <= 4:
        return "Late"
    return "Severely late"
