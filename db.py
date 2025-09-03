# db.py
from __future__ import annotations
import os
import pathlib
import datetime as dt
from typing import Optional, List

import pandas as pd
from sqlalchemy import (
    create_engine, Column, Integer, String, Date, Float, ForeignKey, Text, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Database path (under /data)
ROOT = pathlib.Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_URL = f"sqlite:///{(DATA_DIR / 'leng.db').as_posix()}"

engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
Base = declarative_base()

# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True)
    borrower = Column(String, nullable=False)
    principal = Column(Integer, nullable=False)
    disbursed_on = Column(Date, nullable=False)
    planned_weeks = Column(Integer, nullable=False, default=4)
    processing_fee_pct = Column(Float, nullable=False, default=1.0)  # %
    transaction_charge = Column(Integer, nullable=False, default=0)  # UGX flat

    repayments = relationship("Repayment", back_populates="loan", cascade="all, delete-orphan")

class Repayment(Base):
    __tablename__ = "repayments"
    id = Column(Integer, primary_key=True)
    borrower = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    paid_on = Column(Date, nullable=False)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=True)

    loan = relationship("Loan", back_populates="repayments")

class EquityContribution(Base):
    __tablename__ = "equity_contributions"
    id = Column(Integer, primary_key=True)
    contributor = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    contributed_on = Column(Date, nullable=False)
    note = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)

# ──────────────────────────────────────────────────────────────────────────────
# CRUD helpers
# ──────────────────────────────────────────────────────────────────────────────

def save_loan(
    borrower: str,
    principal: int,
    disbursed_on: dt.date,
    planned_weeks: int,
    processing_fee_pct: float = 1.0,
    transaction_charge: int = 0,
) -> int:
    with SessionLocal() as s:
        loan = Loan(
            borrower=borrower,
            principal=int(principal),
            disbursed_on=disbursed_on,
            planned_weeks=int(planned_weeks),
            processing_fee_pct=float(processing_fee_pct),
            transaction_charge=int(transaction_charge),
        )
        s.add(loan)
        s.commit()
        return loan.id

def save_repayment(
    borrower: str,
    amount: int,
    paid_on: dt.date,
    loan_id: Optional[int] = None,
) -> int:
    with SessionLocal() as s:
        rep = Repayment(
            borrower=borrower,
            amount=int(amount),
            paid_on=paid_on,
            loan_id=loan_id,
        )
        s.add(rep)
        s.commit()
        return rep.id

def save_equity_contribution(
    contributor: str,
    amount: int,
    contributed_on: dt.date,
    note: Optional[str] = None,
) -> int:
    with SessionLocal() as s:
        eq = EquityContribution(
            contributor=contributor,
            amount=int(amount),
            contributed_on=contributed_on,
            note=note,
        )
        s.add(eq)
        s.commit()
        return eq.id

# ──────────────────────────────────────────────────────────────────────────────
# Lists for UI
# ──────────────────────────────────────────────────────────────────────────────

def list_loans_df() -> pd.DataFrame:
    with SessionLocal() as s:
        q = s.query(Loan).order_by(Loan.disbursed_on.desc(), Loan.id.desc())
        rows = [
            {
                "id": r.id,
                "borrower": r.borrower,
                "principal": r.principal,
                "disbursed_on": r.disbursed_on,
                "planned_weeks": r.planned_weeks,
                "processing_fee_pct": r.processing_fee_pct,
                "transaction_charge": r.transaction_charge,
            }
            for r in q.all()
        ]
        return pd.DataFrame(rows)

def list_repayments_df() -> pd.DataFrame:
    with SessionLocal() as s:
        q = s.query(Repayment).order_by(Repayment.paid_on.desc(), Repayment.id.desc())
        rows = [
            {
                "id": r.id,
                "borrower": r.borrower,
                "amount": r.amount,
                "paid_on": r.paid_on,
                "loan_id": r.loan_id,
            }
            for r in q.all()
        ]
        return pd.DataFrame(rows)

def list_equity_df() -> pd.DataFrame:
    with SessionLocal() as s:
        q = s.query(EquityContribution).order_by(EquityContribution.contributed_on.desc(), EquityContribution.id.desc())
        rows = [
            {
                "id": r.id,
                "contributor": r.contributor,
                "amount": r.amount,
                "contributed_on": r.contributed_on,
                "note": r.note,
            }
            for r in q.all()
        ]
        return pd.DataFrame(rows)

def loan_id_choices() -> list[int]:
    with SessionLocal() as s:
        return [i for (i,) in s.query(Loan.id).all()]

# ──────────────────────────────────────────────────────────────────────────────
# Bulk import helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_date(v) -> dt.date:
    if isinstance(v, dt.date):
        return v
    return pd.to_datetime(v).date()

def bulk_import_loans_df(df: pd.DataFrame) -> int:
    required = {"borrower", "principal", "disbursed_on", "planned_weeks"}
    missing = required - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    # normalize columns
    cols = {c: c.lower() for c in df.columns}
    df = df.rename(columns=cols)

    count = 0
    with SessionLocal() as s:
        for _, row in df.iterrows():
            loan = Loan(
                borrower=str(row["borrower"]).strip(),
                principal=int(row["principal"]),
                disbursed_on=_parse_date(row["disbursed_on"]),
                planned_weeks=int(row.get("planned_weeks", 4)),
                processing_fee_pct=float(row.get("processing_fee_pct", 1.0)),
                transaction_charge=int(row.get("transaction_charge", 0) or 0),
            )
            s.add(loan)
            count += 1
        s.commit()
    return count

def bulk_import_repayments_df(df: pd.DataFrame) -> int:
    required = {"borrower", "amount", "paid_on"}
    missing = required - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    cols = {c: c.lower() for c in df.columns}
    df = df.rename(columns=cols)

    count = 0
    with SessionLocal() as s:
        for _, row in df.iterrows():
            rep = Repayment(
                borrower=str(row["borrower"]).strip(),
                amount=int(row["amount"]),
                paid_on=_parse_date(row["paid_on"]),
                loan_id=int(row["loan_id"]) if "loan_id" in df.columns and pd.notna(row.get("loan_id")) else None,
            )
            s.add(rep)
            count += 1
        s.commit()
    return count

def bulk_import_equity_df(df: pd.DataFrame) -> int:
    required = {"contributor", "amount", "contributed_on"}
    missing = required - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    cols = {c: c.lower() for c in df.columns}
    df = df.rename(columns=cols)

    count = 0
    with SessionLocal() as s:
        for _, row in df.iterrows():
            eq = EquityContribution(
                contributor=str(row["contributor"]).strip(),
                amount=int(row["amount"]),
                contributed_on=_parse_date(row["contributed_on"]),
                note=str(row["note"]) if "note" in df.columns and pd.notna(row.get("note")) else None,
            )
            s.add(eq)
            count += 1
        s.commit()
    return count

# ──────────────────────────────────────────────────────────────────────────────
# Reports / Snapshot
# ──────────────────────────────────────────────────────────────────────────────

def portfolio_snapshot() -> dict:
    """
    Estimated cash = Equity + Repayments + Processing Fees − Principal Disbursed − Transaction Charges
    (Interest/penalty recognition is handled in loan_logic; this cash estimate is operational.)
    """
    with SessionLocal() as s:
        # Loans stats
        loans_count = s.query(func.count(Loan.id)).scalar() or 0
        total_principal = s.query(func.coalesce(func.sum(Loan.principal), 0)).scalar() or 0
        total_txn_charges = s.query(func.coalesce(func.sum(Loan.transaction_charge), 0)).scalar() or 0

        # Processing fees (1% * principal, per loan row)
        fees_rows = s.query(Loan.principal, Loan.processing_fee_pct).all()
        total_proc_fees = sum(int(p * (pct / 100.0)) for p, pct in fees_rows)

        # Repayments
        total_repayments = s.query(func.coalesce(func.sum(Repayment.amount), 0)).scalar() or 0

        # Equity
        total_equity = s.query(func.coalesce(func.sum(EquityContribution.amount), 0)).scalar() or 0

        estimated_cash = int(total_equity + total_repayments + total_proc_fees - total_principal - total_txn_charges)

        return dict(
            loans_count=int(loans_count),
            total_principal=int(total_principal),
            total_repayments=int(total_repayments),
            total_equity=int(total_equity),
            total_processing_fees=int(total_proc_fees),
            total_transaction_charges=int(total_txn_charges),
            estimated_cash=estimated_cash,
        )

def simple_aging_df() -> pd.DataFrame:
    today = dt.date.today()
    with SessionLocal() as s:
        rows = s.query(Loan).all()
        data = []
        for r in rows:
            weeks_elapsed = max(0, (today - r.disbursed_on).days // 7)
            data.append(
                dict(
                    id=r.id,
                    borrower=r.borrower,
                    disbursed_on=r.disbursed_on,
                    weeks_elapsed=weeks_elapsed,
                    planned_weeks=r.planned_weeks,
                )
            )
        return pd.DataFrame(data)
