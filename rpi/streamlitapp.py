# rpi/streamlit_app.py
import json
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="Lighthouse Explorer", layout="wide")

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_POINTS_FILE = REPO_ROOT / "server" / "site" / "data.min.json"
DETAILS_FILE = REPO_ROOT / "data" / "lighthousedata.json"

def safe_load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

st.title("Lighthouse Explorer")

col1, col2 = st.columns(2, gap="large")

with col1:
    st.subheader("Start")
    st.write("Open the interactive map and click a marker to see details.")
    if st.button("Open map", type="primary"):
        st.switch_page("pages/1_lighthouse.py")

with col2:
    st.subheader("Status")
    mp = safe_load_json(MAP_POINTS_FILE)
    dd = safe_load_json(DETAILS_FILE)

    if mp is None:
        st.error(f"Cannot read map dataset: {MAP_POINTS_FILE}")
    else:
        st.metric("Map points", f"{len(mp):,}")

    if dd is None:
        st.error(f"Cannot read details dataset: {DETAILS_FILE}")
    else:
        # lighthousedata.json can be list or dict. Just show a rough count.
        if isinstance(dd, list):
            n = len(dd)
        elif isinstance(dd, dict):
            n = len(dd.get("elements", dd.get("items", dd.get("data", [])))) if any(k in dd for k in ("elements","items","data")) else len(dd)
        else:
            n = 0
        st.metric("Detail entries", f"{n:,}")

st.divider()
st.caption("Tip: You can deep-link directly to a lighthouse using ?id=..., for example /?id=n1191075008 on the lighthouse page.")
