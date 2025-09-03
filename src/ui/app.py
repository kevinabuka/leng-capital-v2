# src/ui/app.py
from __future__ import annotations

# ---- Standard libs ----
import os
import sys
import pathlib
import datetime as dt
from typing import Optional

# ---- Third-party ----
import streamlit as st
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# MUST be the first Streamlit call
st.set_page_config(page_title="Leng Capital – Lending App", layout="wide")
# ──────────────────────────────────────────────────────────────────────────────

# Ensure the repo root is importable (so `db.py` and `loan_logic.py` can be found)
ROOT = pathlib.Path(__file__).resolve().parents[2]  # <repo_root>/...
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Try imports but don't call st.* in except blocks (collect warnings instead)
warnings: list[str] = []
try:
    import db
except Exception as e:
    db = None  # type: ignore
    warnings.append(f"db.py not loaded: {e}")

try:
    import loan_logic
except Exception as e:
    loan_logic = None  # type: ignore
    warnings.append(f"loan_logic.py not loaded: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_db():
    if db is None:
        st.stop()

def _df_preview(df: pd.DataFrame, n: int = 8):
    st.caption("Preview (first rows)")
    st.dataframe(df.head(n), use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────────────────────────────────────
st.title("Leng Capital – Lending App")

# Show any import warnings in the sidebar
if warnings:
    with st.sidebar:
        for w in warnings:
            st.warning(w)

with st.expander("Environment", expanded=False):
    st.json(
        {
            "python": os.popen("python -V").read().strip() or "unknown",
            "repo_root": str(ROOT),
            "modules": {
                "db_loaded": db is not None,
                "loan_logic_loaded": loan_logic is not None,
            },
            "database": getattr(db, "DB_URL", "unknown") if db else "n/a",
        }
    )

tab_loans, tab_repayments, tab_equity, tab_reports, tab_import, tab_settings = st.tabs(
    ["Loans", "Repayments", "Equity", "Reports", "Import", "Settings"]
)

# ---- Loans tab ----
with tab_loans:
    st.subheader("Disburse a Loan")

    _ensure_db()

    with st.form("new_loan"):
        col1, col2, col3 = st.columns(3)
        borrower = col1.text_input("Borrower name *")
        principal = col2.number_input("Principal (UGX) *", min_value=0, step=10_000)
        weeks = col3.number_input("Planned weeks", min_value=1, value=4)

        col4, col5, col6 = st.columns(3)
        disbursed_on = col4.date_input("Disbursement date", value=dt.date.today())
        processing_fee_pct = col5.number_input("Processing fee (%)", value=1.0, step=0.1)
        transaction_charge = col6.number_input("Transaction charge per disbursement (UGX)", min_value=0, value=0, step=100)

        submitted = st.form_submit_button("Save loan")

    if submitted:
        if not borrower or principal <= 0:
            st.error("Borrower and principal are required.")
        else:
            try:
                db.save_loan(
                    borrower=borrower,
                    principal=int(principal),
                    disbursed_on=disbursed_on,
                    planned_weeks=int(weeks),
                    processing_fee_pct=float(processing_fee_pct),
                    transaction_charge=int(transaction_charge),
                )
                st.success("Loan saved.")
            except Exception as e:
                st.error(f"Error saving loan: {e}")

    st.divider()
    st.subheader("Amount Due Preview")
    if loan_logic and hasattr(loan_logic, "amount_due"):
        P = st.number_input(
            "Preview principal (UGX)", min_value=0, value=200_000, step=10_000
        )
        w = st.number_input("Weeks elapsed", min_value=0, value=3)
        try:
            preview = loan_logic.amount_due(P=int(P), weeks_elapsed=int(w))  # type: ignore
            st.metric("Estimated amount due", f"{int(preview):,} UGX")
        except Exception as e:
            st.error(f"Error computing amount due: {e}")
    else:
        st.caption(
            "Load `loan_logic.py` with `amount_due(P, weeks_elapsed)` to enable this preview."
        )

    st.divider()
    st.subheader("Active Loans")
    try:
        loans_df = db.list_loans_df()
        st.dataframe(loans_df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading loans: {e}")

# ---- Repayments tab ----
with tab_repayments:
    st.subheader("Record a Repayment")

    _ensure_db()

    with st.form("new_repayment"):
        col1, col2, col3 = st.columns(3)
        borrower_r = col1.text_input("Borrower name *")
        amount = col2.number_input("Amount (UGX) *", min_value=0, step=10_000)
        paid_on = col3.date_input("Payment date", value=dt.date.today())
        loan_id_opt = st.selectbox("Link to Loan (optional)", options=[None] + db.loan_id_choices(), index=0, format_func=lambda x: "—" if x is None else f"Loan #{x}")
        submit_pay = st.form_submit_button("Save repayment")

    if submit_pay:
        if not borrower_r or amount <= 0:
            st.error("Borrower and amount are required.")
        else:
            try:
                db.save_repayment(
                    borrower=borrower_r,
                    amount=int(amount),
                    paid_on=paid_on,
                    loan_id=loan_id_opt,
                )
                st.success("Repayment saved.")
            except Exception as e:
                st.error(f"Error saving repayment: {e}")

    st.divider()
    st.subheader("Recent Repayments")
    try:
        reps_df = db.list_repayments_df()
        st.dataframe(reps_df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading repayments: {e}")

# ---- Equity tab ----
with tab_equity:
    st.subheader("Record Equity Contribution")

    _ensure_db()

    with st.form("new_equity"):
        col1, col2, col3 = st.columns(3)
        contributor = col1.text_input("Contributor *")
        eq_amount = col2.number_input("Amount (UGX) *", min_value=0, step=50_000)
        eq_date = col3.date_input("Contribution date", value=dt.date.today())
        note = st.text_input("Note / Purpose (optional)")
        submit_eq = st.form_submit_button("Save equity contribution")

    if submit_eq:
        if not contributor or eq_amount <= 0:
            st.error("Contributor and positive amount are required.")
        else:
            try:
                db.save_equity_contribution(
                    contributor=contributor,
                    amount=int(eq_amount),
                    contributed_on=eq_date,
                    note=note or None,
                )
                st.success("Equity contribution saved.")
            except Exception as e:
                st.error(f"Error saving equity: {e}")

    st.divider()
    st.subheader("Equity Register")
    try:
        eq_df = db.list_equity_df()
        st.dataframe(eq_df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading equity: {e}")

# ---- Reports tab ----
with tab_reports:
    st.subheader("Portfolio Snapshot")

    _ensure_db()

    try:
        snap = db.portfolio_snapshot()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Loans Disbursed (count)", f"{snap['loans_count']:,}")
        c2.metric("Total Principal Disbursed", f"{int(snap['total_principal']):,} UGX")
        c3.metric("Total Repayments", f"{int(snap['total_repayments']):,} UGX")
        c4.metric("Total Equity Contributed", f"{int(snap['total_equity']):,} UGX")
        c5.metric("Est. Cash Position*", f"{int(snap['estimated_cash']):,} UGX")

        st.caption("*Estimated cash = Equity + Repayments + Processing Fees − Principal Disbursed − Transaction Charges")
    except Exception as e:
        st.error(f"Error loading snapshot: {e}")

    st.divider()
    st.subheader("Aging (Simple View)")
    st.caption("Shows weeks since disbursement; detailed schedule can be added later.")
    try:
        aging = db.simple_aging_df()
        st.dataframe(aging, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading aging: {e}")

# ---- Import tab ----
with tab_import:
    st.subheader("Bulk Import")

    _ensure_db()

    st.markdown("**Loans Import** — CSV or Excel with columns: `borrower, principal, disbursed_on, planned_weeks, processing_fee_pct, transaction_charge`")
    file_loans = st.file_uploader("Upload loans file", type=["csv", "xlsx"], key="loans_upload")
    if file_loans is not None:
        try:
            if file_loans.name.endswith(".csv"):
                df = pd.read_csv(file_loans)
            else:
                df = pd.read_excel(file_loans)
            _df_preview(df)
            if st.button("Import loans now"):
                count = db.bulk_import_loans_df(df)
                st.success(f"Imported {count} loans.")
        except Exception as e:
            st.error(f"Import failed: {e}")

    st.divider()
    st.markdown("**Repayments Import** — CSV or Excel with columns: `borrower, amount, paid_on, loan_id (optional)`")
    file_reps = st.file_uploader("Upload repayments file", type=["csv", "xlsx"], key="reps_upload")
    if file_reps is not None:
        try:
            if file_reps.name.endswith(".csv"):
                df = pd.read_csv(file_reps)
            else:
                df = pd.read_excel(file_reps)
            _df_preview(df)
            if st.button("Import repayments now"):
                count = db.bulk_import_repayments_df(df)
                st.success(f"Imported {count} repayments.")
        except Exception as e:
            st.error(f"Import failed: {e}")

    st.divider()
    st.markdown("**Equity Import** — CSV or Excel with columns: `contributor, amount, contributed_on, note (optional)`")
    file_eq = st.file_uploader("Upload equity file", type=["csv", "xlsx"], key="eq_upload")
    if file_eq is not None:
        try:
            if file_eq.name.endswith(".csv"):
                df = pd.read_csv(file_eq)
            else:
                df = pd.read_excel(file_eq)
            _df_preview(df)
            if st.button("Import equity now"):
                count = db.bulk_import_equity_df(df)
                st.success(f"Imported {count} equity contributions.")
        except Exception as e:
            st.error(f"Import failed: {e}")

# ---- Settings tab ----
with tab_settings:
    st.subheader("Business Rules (read-only in this version)")
    st.write(
        """
        - Weekly interest: **10%** (compounded weekly for preview).
        - Late penalty: **+2.5% of principal** for each **additional unpaid week** (beyond week 1).
        - Processing fee: **1%** of principal, charged upfront.
        - Transaction charge: per-disbursement cash cost (UGX).
        """
    )
    st.caption("We can add editable controls and persist them if you’d like.")
