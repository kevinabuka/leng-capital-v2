# src/ui/app.py

# ---------------------------
# Startup error catcher (shows real traceback in the browser)
# ---------------------------
import streamlit as st
import sys, os, traceback
from pathlib import Path

def run_safely(fn):
    try:
        fn()
    except Exception:
        st.error("App failed to start")
        st.code("".join(traceback.format_exception(*sys.exc_info())))
        st.stop()

# ---------------------------
# Application
# ---------------------------
def main():
    # Basic page config
    st.set_page_config(page_title="Leng Capital", page_icon="💸", layout="centered")

    # Make sure local imports work with a src/ layout:
    # add the repo root to sys.path (…/leng-capital)
    here = Path(__file__).resolve()
    repo_root = here.parents[2]  # src/ui/app.py -> ui -> src -> <repo root>
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))

    st.title("Leng Capital – Lending App")
    st.caption("Basic bootstrap to surface runtime errors and verify environment.")

    # Environment panel
    with st.expander("Environment & Paths", expanded=True):
        st.write(
            {
                "Python": sys.version.split()[0],
                "App file": str(here),
                "Working dir (os.getcwd())": os.getcwd(),
                "Repo root (detected)": str(repo_root),
            }
        )

    # Check pandas availability
    pandas_ok = False
    try:
        import pandas as pd  # noqa: F401
        pandas_ok = True
        st.success("✅ pandas is installed and importable.")
        st.write({"pandas_version": pd.__version__})
    except Exception as e:
        st.warning(
            "⚠️ pandas could not be imported. "
            "On Streamlit Cloud this usually means the Python version is wrong or wheels are missing. "
            "Ensure `runtime.txt` contains `3.12.6` and that you redeployed."
        )
        st.code(repr(e))

    # Optional: quick data viewer if you have a seed file
    st.subheader("Optional data check")
    st.write(
        "If you have a CSV at `data/seed.csv`, I’ll try to show its first few rows. "
        "This is optional and won’t crash if the file is missing."
    )
    seed_csv = repo_root / "data" / "seed.csv"
    if seed_csv.exists() and pandas_ok:
        import pandas as pd

        try:
            df = pd.read_csv(seed_csv)
            st.write(f"Found `{seed_csv}` with shape {df.shape}:")
            st.dataframe(df.head(25))
        except Exception as e:
            st.warning("Could not read `data/seed.csv`:")
            st.code("".join(traceback.format_exception(*sys.exc_info())))
    else:
        if not seed_csv.exists():
            st.info("`data/seed.csv` not found (that’s OK).")

    # Placeholder for your actual app UI
    st.markdown("---")
    st.subheader("Your App Area")
    st.write(
        "Replace this section with your lending UI (forms, tables, charts). "
        "This scaffold is only to make deployment smooth and errors visible."
    )

if __name__ == "__main__":
    run_safely(main)
