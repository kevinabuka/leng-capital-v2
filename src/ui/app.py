# src/ui/app.py
from __future__ import annotations

# ---- Standard libs ----
import os
import sys
import pathlib
import datetime as dt

# ---- Streamlit ----
import streamlit as st

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
# UI
# ──────────────────────────────────────────────────────────────────────────────
st.title("Leng Capital – Lending App")

# Show any import warnings in the sidebar
if warnings:
    with st.sidebar:
        for w in warnings:
            st.warning(w)

# Optional tiny env peek (handy when debugging)
with st.expander("Environment", expanded=False):
    st.json(
        {
            "python": os.popen("python -V").read().strip() or "unknown",
            "repo_root": str(ROOT),
            "modules": {
                "db_loaded": db is not None,
                "loan_logic_loaded": loan_logic is not None,
            },
        }
    )

tab_loans, tab_repayments, tab_reports, tab_settings = st.tabs(
    ["Loans", "Repayments", "Reports", "Settings"]
)

# ---- Loans tab ----
with tab_loans:
    st.subheader("Disburse a Loan")

    with st.form("new_loan"):
        borrower = st.text_input("Borrower name *")
        principal = st.number_input("Principal (UGX) *", min_value=0, step=10_000)
        disbursed_on = st.date_input("Disbursement date", value=dt.date.today())
        weeks = st.number_input("Planned weeks", min_value=1, value=4)
        processing_fee_pct = st.number_input("Processing fee (%)", value=1.0, step=0.1)
        submitted = st.form_submit_button("Save loan")

    if submitted:
        if not borrower or principal <= 0:
            st.error("Borrower and principal are required.")
        else:
            if db and hasattr(db, "save_loan"):
                try:
                    db.save_loan(
                        borrower=borrower,
                        principal=int(principal),
                        disbursed_on=disbursed_on,
                        weeks=int(weeks),
                        processing_fee_pct=float(processing_fee_pct),
                    )
                    st.success("Loan saved.")
                except Exception as e:
                    st.error(f"Error saving loan: {e}")
            else:
                st.info("Demo mode: db.save_loan not available; nothing was written.")

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

# ---- Repayments tab ----
with tab_repayments:
    st.subheader("Record a Repayment")

    with st.form("new_repayment"):
        borrower_r = st.text_input("Borrower name *")
        amount = st.number_input("Amount (UGX) *", min_value=0, step=10_000)
        paid_on = st.date_input("Payment date", value=dt.date.today())
        submit_pay = st.form_submit_button("Save repayment")

    if submit_pay:
        if not borrower_r or amount <= 0:
            st.error("Borrower and amount are required.")
        else:
            if db and hasattr(db, "save_repayment"):
                try:
                    db.save_repayment(
                        borrower=borrower_r, amount=int(amount), paid_on=paid_on
                    )
                    st.success("Repayment saved.")
                except Exception as e:
                    st.error(f"Error saving repayment: {e}")
            else:
                st.info(
                    "Demo mode: db.save_repayment not available; nothing was written."
                )

# ---- Reports tab ----
with tab_reports:
    st.subheader("Portfolio Snapshot")
    if db and hasattr(db, "portfolio_snapshot"):
        try:
            snap = db.portfolio_snapshot()
            st.write(snap)
        except Exception as e:
            st.error(f"Error loading snapshot: {e}")
    else:
        st.info("Add `portfolio_snapshot()` in db.py to show live stats.")

# ---- Settings tab ----
with tab_settings:
    st.subheader("App Settings")
    st.caption("Place configuration controls here (rates, penalties, etc.).")
