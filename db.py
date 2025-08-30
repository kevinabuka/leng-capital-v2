# ---- db.py (top) ----
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

def _default_sqlite_path() -> str:
    """
    Use a writeable location:
    - On Streamlit Cloud: /mount/data/lending.db (writeable & persists across restarts)
    - Locally: src/../lending.db (your current behavior)
    """
    # Streamlit Cloud has /mount/data
    if os.path.isdir("/mount/data"):
        return os.path.join("/mount/data", "lending.db")
    # local fallback
    return os.path.join(os.path.dirname(__file__), "..", "lending.db")

# Prefer a hosted DB if provided via secrets
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DB_URL = DATABASE_URL  # e.g., postgresql+psycopg://USER:PASSWORD@HOST/DBNAME
else:
    # Allow overriding, but default to a writeable path
    DB_PATH = os.environ.get("LENDING_DB_PATH", _default_sqlite_path())
    DB_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"

engine: Engine = create_engine(DB_URL, future=True, pool_pre_ping=True)


# ---------------- Schema ----------------
SCHEMA_STATEMENTS = [
    # loans
    """
    CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT,
        last_name TEXT,
        borrower TEXT, -- legacy
        principal REAL NOT NULL,
        disbursed_on TEXT NOT NULL,
        tx_charge REAL DEFAULT 0.0,
        notes TEXT,
        term_weeks INTEGER DEFAULT 1,
        agreed_due_on TEXT,
        written_off_on TEXT,
        write_off_amount REAL DEFAULT 0.0
    );
    """,
    # payments
    """
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        paid_on TEXT NOT NULL,
        method TEXT DEFAULT '',
        notes TEXT,
        FOREIGN KEY (loan_id) REFERENCES loans(id)
    );
    """,
    # shareholders (id + name)
    """
    CREATE TABLE IF NOT EXISTS shareholders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );
    """,
    # equity injections
    """
    CREATE TABLE IF NOT EXISTS equity_injections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        injected_on TEXT NOT NULL,
        notes TEXT,
        shareholder_id INTEGER,
        FOREIGN KEY (shareholder_id) REFERENCES shareholders(id)
    );
    """,
    # other income (cash)
    """
    CREATE TABLE IF NOT EXISTS other_income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        earned_on TEXT NOT NULL,
        category TEXT DEFAULT '',
        notes TEXT
    );
    """
]

def init_db():
    with engine.begin() as con:
        for stmt in SCHEMA_STATEMENTS:
            con.execute(text(stmt))

# ---------------- Loans ----------------
def insert_loan(first_name, last_name, principal, disbursed_on, tx_charge, notes, term_weeks: int):
    agreed_due_on = None
    if term_weeks and int(term_weeks) > 0:
        from datetime import date, timedelta
        d = datetime.fromisoformat(disbursed_on).date()
        agreed_due_on = (d + timedelta(days=7 * int(term_weeks))).isoformat()
    with engine.begin() as con:
        con.execute(
            text("""
                INSERT INTO loans
                    (first_name, last_name, borrower, principal, disbursed_on, tx_charge, notes, term_weeks, agreed_due_on)
                VALUES (:fn, :ln, :bor, :p, :d, :t, :n, :tw, :due)
            """),
            {"fn": first_name, "ln": last_name, "bor": f"{first_name} {last_name}".strip(),
             "p": principal, "d": disbursed_on, "t": tx_charge, "n": notes, "tw": int(term_weeks), "due": agreed_due_on}
        )

def update_loan(loan_id, first_name, last_name, principal, disbursed_on, tx_charge, notes, term_weeks: int | None):
    agreed_due_on = None
    if term_weeks and int(term_weeks) > 0:
        from datetime import date, timedelta
        d = datetime.fromisoformat(disbursed_on).date()
        agreed_due_on = (d + timedelta(days=7 * int(term_weeks))).isoformat()
    with engine.begin() as con:
        con.execute(
            text("""
                UPDATE loans SET
                    first_name=:fn, last_name=:ln, borrower=:bor,
                    principal=:p, disbursed_on=:d, tx_charge=:t,
                    notes=:n, term_weeks=:tw, agreed_due_on=:due
                WHERE id=:id
            """),
            {"fn": first_name, "ln": last_name, "bor": f"{first_name} {last_name}".strip(),
             "p": principal, "d": disbursed_on, "t": tx_charge, "n": notes, "tw": int(term_weeks or 1),
             "due": agreed_due_on, "id": loan_id}
        )

def fetch_loans():
    with engine.begin() as con:
        rows = con.execute(text("SELECT * FROM loans ORDER BY id DESC")).mappings().all()
        return [dict(r) for r in rows]

def delete_loan(loan_id: int):
    with engine.begin() as con:
        con.execute(text("DELETE FROM payments WHERE loan_id=:id"), {"id": loan_id})
        con.execute(text("DELETE FROM loans WHERE id=:id"), {"id": loan_id})

# ---------------- Payments ----------------
def insert_payment(loan_id, amount, paid_on, method, notes):
    with engine.begin() as con:
        con.execute(
            text("INSERT INTO payments (loan_id, amount, paid_on, method, notes) VALUES (:l, :a, :p, :m, :n)"),
            {"l": loan_id, "a": amount, "p": paid_on, "m": method, "n": notes}
        )

def update_payment(payment_id, amount, paid_on, method, notes):
    with engine.begin() as con:
        con.execute(
            text("UPDATE payments SET amount=:a, paid_on=:p, method=:m, notes=:n WHERE id=:id"),
            {"a": amount, "p": paid_on, "m": method, "n": notes, "id": payment_id}
        )

def delete_payment(payment_id):
    with engine.begin() as con:
        con.execute(text("DELETE FROM payments WHERE id=:id"), {"id": payment_id})

def fetch_payments_by_loan(loan_id):
    with engine.begin() as con:
        rows = con.execute(
            text("SELECT * FROM payments WHERE loan_id=:l ORDER BY paid_on ASC, id ASC"),
            {"l": loan_id}
        ).mappings().all()
        return [dict(r) for r in rows]

def fetch_all_payments():
    with engine.begin() as con:
        rows = con.execute(text("SELECT * FROM payments ORDER BY paid_on ASC, id ASC")).mappings().all()
        return [dict(r) for r in rows]

# ---------------- Shareholders & Equity ----------------
def insert_shareholder(name: str):
    with engine.begin() as con:
        con.execute(text("INSERT OR IGNORE INTO shareholders (name) VALUES (:n)"), {"n": name})

def fetch_shareholders():
    with engine.begin() as con:
        rows = con.execute(text("SELECT id, name FROM shareholders ORDER BY name ASC")).mappings().all()
        return [dict(r) for r in rows]

def insert_equity(amount: float, injected_on: str, notes: str = "", shareholder_id: int | None = None):
    with engine.begin() as con:
        con.execute(
            text("""
                INSERT INTO equity_injections (amount, injected_on, notes, shareholder_id)
                VALUES (:a, :d, :n, :sid)
            """),
            {"a": amount, "d": injected_on, "n": notes, "sid": shareholder_id}
        )

def fetch_equity():
    with engine.begin() as con:
        rows = con.execute(text("""
            SELECT e.id, e.amount, e.injected_on, e.notes, e.shareholder_id,
                   s.name AS shareholder_name
            FROM equity_injections e
            LEFT JOIN shareholders s ON s.id = e.shareholder_id
            ORDER BY e.injected_on ASC, e.id ASC
        """)).mappings().all()
        return [dict(r) for r in rows]

def update_equity(equity_id: int, amount: float, injected_on: str, notes: str, shareholder_id: int | None):
    with engine.begin() as con:
        con.execute(
            text("""
                UPDATE equity_injections
                SET amount=:a, injected_on=:d, notes=:n, shareholder_id=:sid
                WHERE id=:id
            """),
            {"a": amount, "d": injected_on, "n": notes, "sid": shareholder_id, "id": equity_id}
        )

def delete_equity(equity_id: int):
    with engine.begin() as con:
        con.execute(text("DELETE FROM equity_injections WHERE id=:id"), {"id": equity_id})

# ---------------- Other Income ----------------
def insert_other_income(amount: float, earned_on: str, category: str, notes: str):
    with engine.begin() as con:
        con.execute(
            text("INSERT INTO other_income (amount, earned_on, category, notes) VALUES (:a, :d, :c, :n)"),
            {"a": amount, "d": earned_on, "c": category, "n": notes}
        )

def fetch_other_income():
    with engine.begin() as con:
        rows = con.execute(text("SELECT * FROM other_income ORDER BY earned_on ASC, id ASC")).mappings().all()
        return [dict(r) for r in rows]

# ---------------- Write-offs ----------------
def set_write_off(loan_id: int, written_off_on: str, amount: float):
    with engine.begin() as con:
        con.execute(
            text("UPDATE loans SET written_off_on=:d, write_off_amount=:a WHERE id=:id"),
            {"d": written_off_on, "a": amount, "id": loan_id}
        )

def clear_write_off(loan_id: int):
    with engine.begin() as con:
        con.execute(
            text("UPDATE loans SET written_off_on=NULL, write_off_amount=0.0 WHERE id=:id"),
            {"id": loan_id}
        )
