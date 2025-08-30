from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil
from typing import Iterable, Dict, Any, Optional, List


@dataclass
class Payment:
    amount: float
    paid_on: date


def _ceil_weeks(days: int) -> int:
    if days <= 0:
        return 0
    return ceil(days / 7)


def overdue_weeks(as_of: date, due_on: Optional[date], disbursed_on: date) -> int:
    """# of started overdue weeks. 0 if not yet overdue or no due date."""
    if not due_on or as_of <= due_on:
        return 0
    return _ceil_weeks((as_of - due_on).days)


def aging_bucket(ov_weeks: int) -> str:
    if ov_weeks <= 0:
        return "Current"
    if 1 <= ov_weeks <= 2:
        return "1–2w"
    if 3 <= ov_weeks <= 4:
        return "3–4w"
    return "5+w"


def scheduled_due_on_date(
    *,
    principal: float,
    disbursed_on: date,
    due_on: date,
    weekly_interest_rate: float = 0.10,
    processing_fee_rate: float = 0.01,
) -> Dict[str, float]:
    """Preview for creation/editor: amount due on agreed date; fee is deducted upfront."""
    weeks = max(1, _ceil_weeks((due_on - disbursed_on).days))
    base_interest = principal * weekly_interest_rate * weeks
    processing_fee_upfront = principal * processing_fee_rate
    scheduled_due_amount = principal + base_interest  # no late in the preview
    net_cash_to_borrower = principal - processing_fee_upfront
    return {
        "weeks": weeks,
        "scheduled_due_amount": round(scheduled_due_amount, 2),
        "processing_fee_upfront": round(processing_fee_upfront, 2),
        "net_cash_to_borrower": round(net_cash_to_borrower, 2),
    }


def amount_due_with_payments(
    *,
    principal: float,
    disbursed_on: date,
    as_of: date,
    payments: Iterable[Dict[str, Any]] | Iterable[Payment],
    weekly_interest_rate: float = 0.10,
    processing_fee_rate: float = 0.01,     # informational
    tx_charge_expense: float = 0.0,        # informational
    late_step_rate: float = 0.025,
    term_weeks: Optional[int] = None,
    agreed_due_on: Optional[date] = None,
) -> Dict[str, float]:
    """
    Accrues week-by-week and applies each payment immediately (interest -> late -> principal).
    - Pre-due: each started week adds principal_remaining * weekly_interest_rate.
    - Post-due: for started overdue week k, add principal_remaining * weekly_interest_rate to interest,
                and principal_remaining * (k * late_step_rate) to late (increment applied immediately).
    - If a payment fully clears interest+late+principal on its date, accrual stops after that date.

    Returns:
      principal_receivable        Capital still owed (after payments)
      accrued_interest_fees       Interest + late accrued but unpaid
      outstanding                 Sum of the above
      principal                   (alias of principal_receivable)
      interest                    Total accrued base interest through effective cutoff
      late_incremental            Total accrued late through effective cutoff
    """
    # Normalize payments: only consider those on/before as_of, sorted
    pays: List[Payment] = []
    for p in payments:
        if isinstance(p, dict):
            pays.append(
                Payment(
                    amount=float(p["amount"]),
                    paid_on=p["paid_on"] if isinstance(p["paid_on"], date) else date.fromisoformat(str(p["paid_on"]))
                )
            )
        else:
            pays.append(p)
    pays = [p for p in pays if p.paid_on <= as_of]
    pays.sort(key=lambda x: (x.paid_on, x.amount))

    # Determine due date / term with SAFE DEFAULTS
    # If both missing, default to a 1-week loan to avoid runaway accrual.
    if agreed_due_on is None and term_weeks is None:
        term_weeks = 1
        agreed_due_on = disbursed_on + timedelta(days=7)
    elif agreed_due_on is None and term_weeks is not None:
        agreed_due_on = disbursed_on + timedelta(days=7 * int(term_weeks))
    elif term_weeks is None and agreed_due_on is not None:
        term_weeks = max(1, _ceil_weeks((agreed_due_on - disbursed_on).days))

    # State
    principal_rem = float(principal)
    accrued_interest = 0.0
    accrued_late = 0.0

    # Track which pre-due and overdue "started weeks" have already been charged
    pre_charged_weeks = 0  # relative to disbursed_on
    over_charged_weeks = 0  # relative to agreed_due_on

    # Helper: apply a payment to accrued interest -> accrued late -> principal
    def _apply_payment(amount: float):
        nonlocal accrued_interest, accrued_late, principal_rem
        amt = float(amount)
        # interest first
        take_i = min(accrued_interest, amt); accrued_interest -= take_i; amt -= take_i
        # then late
        take_l = min(accrued_late, amt);    accrued_late    -= take_l;  amt -= take_l
        # then principal
        take_p = min(principal_rem, amt);   principal_rem   -= take_p
        # residue ignored
        return take_i, take_l, take_p

    def _process_accrual_until(target: date):
        """Accrue from last processed state up to 'target' by counting newly-started weeks.
           Charges post immediately at the start of each week (both pre-due and overdue)."""
        nonlocal pre_charged_weeks, over_charged_weeks, accrued_interest, accrued_late, principal_rem

        # ---- Pre-due weeks (from disbursed_on), capped at term_weeks ----
        pre_limit_date = min(target, agreed_due_on) if agreed_due_on else target
        total_pre_started = _ceil_weeks((pre_limit_date - disbursed_on).days)
        total_pre_started = max(0, min(total_pre_started, term_weeks or total_pre_started))
        while pre_charged_weeks < total_pre_started:
            pre_charged_weeks += 1
            if principal_rem > 1e-9:
                accrued_interest += principal_rem * weekly_interest_rate

        # ---- Overdue weeks (after agreed_due_on) ----
        if agreed_due_on and target > agreed_due_on:
            total_over_started = _ceil_weeks((target - agreed_due_on).days)
            while over_charged_weeks < total_over_started:
                over_charged_weeks += 1
                if principal_rem > 1e-9:
                    accrued_interest += principal_rem * weekly_interest_rate
                    accrued_late += principal_rem * (over_charged_weeks * late_step_rate)

    # Walk events (payments by date), accruing just before applying same-day payments.
    idx = 0
    n = len(pays)
    settled = False

    while idx < n and not settled:
        pdate = pays[idx].paid_on
        _process_accrual_until(pdate)

        # Apply all payments on this date
        while idx < n and pays[idx].paid_on == pdate:
            _apply_payment(pays[idx].amount)
            idx += 1

        # If cleared on this date, stop accruing beyond it
        if principal_rem <= 1e-9 and (accrued_interest + accrued_late) <= 1e-9:
            settled = True
            break

    # If not settled, accrue up to as_of
    if not settled:
        _process_accrual_until(as_of)

    principal_receivable = round(max(0.0, principal_rem), 2)
    accrued_interest_fees = round(max(0.0, accrued_interest + accrued_late), 2)
    outstanding_total = round(principal_receivable + accrued_interest_fees, 2)

    return {
        "principal_receivable": principal_receivable,
        "accrued_interest_fees": accrued_interest_fees,
        "outstanding": outstanding_total,
        # legacy/compat keys for existing UI usage
        "principal": principal_receivable,
        "interest": round(accrued_interest, 2),
        "late_incremental": round(accrued_late, 2),
    }
