# rpi/pages/1_lighthouse.py

import json
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Lighthouse Map", layout="wide")

REPO_ROOT = Path(__file__).resolve().parents[2]

MAP_POINTS_FILE = REPO_ROOT / "server" / "site" / "data.min.json"
RPI_APP_JS = REPO_ROOT / "rpi" / "app.js"
DETAILS_FILE = REPO_ROOT / "data" / "lighthousedata.json"

@st.cache_data
def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def load_text(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def normalize_details_items(obj) -> list[dict]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("elements", "items", "data"):
            v = obj.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        vals = list(obj.values())
        if vals and all(isinstance(x, dict) for x in vals):
            return vals
    return []

def osm_key_from_type_id(osm_type: str | None, osm_id) -> str:
    if not osm_type or osm_id is None:
        return ""
    t = str(osm_type).strip().lower()
    prefix = t[:1]
    if prefix not in {"n", "w", "r"}:
        return ""
    return f"{prefix}{osm_id}"

def point_key_from_map_point(p: dict) -> str:
    if p.get("key"):
        return str(p["key"])
    if p.get("osm_type") and (p.get("osm_id") is not None or p.get("id") is not None):
        return str(p["osm_type"])[0] + str(p.get("osm_id", p.get("id")))
    if p.get("type") and p.get("id") is not None:
        return str(p["type"])[0] + str(p["id"])
    return ""

def point_key_from_details_item(item: dict) -> str:
    return osm_key_from_type_id(item.get("type"), item.get("id"))

_sector_key_re = re.compile(r"^seamark:light:(\d+):(.+)$")

def parse_light_sectors(tags: dict) -> list[dict]:
    sectors: dict[int, dict] = {}
    for k, v in (tags or {}).items():
        m = _sector_key_re.match(str(k))
        if not m:
            continue
        idx = int(m.group(1))
        field = m.group(2)
        sectors.setdefault(idx, {})[field] = v

    out = []
    for idx in sorted(sectors.keys()):
        s = sectors[idx]
        out.append(
            {
                "light": idx,
                "character": s.get("character", ""),
                "colour": s.get("colour", ""),
                "sequence": s.get("sequence", ""),
                "period": s.get("period", ""),
                "range": s.get("range", ""),
                "height": s.get("height", ""),
                "sector_start": s.get("sector_start", ""),
                "sector_end": s.get("sector_end", ""),
            }
        )
    return out

def has_unindexed_light(tags: dict) -> bool:
    # seamark:light:colour, seamark:light:period etc, but not seamark:light:<n>:...
    for k in (tags or {}).keys():
        ks = str(k)
        if ks.startswith("seamark:light:") and _sector_key_re.match(ks) is None:
            return True
    return False

def first_light_index(tags: dict) -> int | None:
    if not isinstance(tags, dict):
        return None
    if has_unindexed_light(tags):
        return 0
    if any(str(k).startswith("seamark:light:1:") for k in tags.keys()):
        return 1
    idxs = set()
    for k in tags.keys():
        m = _sector_key_re.match(str(k))
        if m:
            idxs.add(int(m.group(1)))
    return min(idxs) if idxs else None

def main_light_fields(tags: dict) -> dict:
    idx = first_light_index(tags)
    if idx is None:
        return {"main_light": "", "main_colour": "", "main_frequency": "", "main_character": ""}

    if idx == 0:
        character = tags.get("seamark:light:character", "")
        colour = tags.get("seamark:light:colour", "")
        period = tags.get("seamark:light:period", "")
        freq = f"{period} s" if period != "" else ""
        return {
            "main_light": "single",
            "main_colour": colour,
            "main_frequency": freq,
            "main_character": character,
        }

    base = f"seamark:light:{idx}:"
    character = tags.get(base + "character", "")
    colour = tags.get(base + "colour", "")
    period = tags.get(base + "period", "")
    freq = f"{period} s" if period != "" else ""

    return {
        "main_light": str(idx),
        "main_colour": colour,
        "main_frequency": freq,
        "main_character": character,
    }

missing = [str(p) for p in (MAP_POINTS_FILE, RPI_APP_JS, DETAILS_FILE) if not p.exists()]
if missing:
    st.error("Missing required file(s):")
    for m in missing:
        st.write("-", m)
    st.stop()

map_points = load_json(MAP_POINTS_FILE)
app_js = load_text(RPI_APP_JS)

raw_details = load_json(DETAILS_FILE)
details_items = normalize_details_items(raw_details)

map_points_by_key = {point_key_from_map_point(p): p for p in map_points if point_key_from_map_point(p)}
details_by_key = {point_key_from_details_item(it): it for it in details_items if point_key_from_details_item(it)}

# Poll query params updated by JS (no reload)
st_autorefresh(interval=300, key="url_poll")

selected_id = st.query_params.get("id", None)

st.title("Lighthouse map")

left, right = st.columns([2.2, 1], gap="large")

with left:
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    html, body {{ height: 100%; margin: 0; }}
    #map {{ height: 78vh; width: 100%; }}
  </style>
</head>
<body>
  <div id="map"></div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

  <script>
    window.POINTS = {json.dumps(map_points)};
  </script>

  <script>
    {app_js}
  </script>
</body>
</html>
"""
    components.html(html, height=650, scrolling=False)

with right:
    st.subheader("Details")

    if not selected_id:
        st.info("Click a marker to show details.")
        st.stop()

    details = details_by_key.get(selected_id)
    map_point = map_points_by_key.get(selected_id)

    if not details and not map_point:
        st.error(f"ID not found: {selected_id}")
        st.stop()

    if details:
        tags = details.get("tags", {}) or {}

        name = (
            tags.get("seamark:name")
            or tags.get("name")
            or tags.get("name:en")
            or tags.get("name:de")
            or "Unnamed"
        )

        st.write("**Name:**", name)
        st.write("**ID:**", selected_id)
        st.write("**Type:**", details.get("type", ""))
        st.write("**OSM ID:**", details.get("id", ""))

        if map_point:
            st.write("**Lat/Lon:**", map_point.get("lat"), map_point.get("lon"))

        operator = tags.get("operator") or tags.get("seamark:operator")
        if operator:
            st.write("**Operator:**", operator)

        seamark_type = tags.get("seamark:type")
        if seamark_type:
            st.write("**Seamark type:**", seamark_type)

        ref = tags.get("seamark:light:reference")
        if ref:
            st.write("**Light reference:**", ref)

        ml = main_light_fields(tags)
        if ml.get("main_colour") or ml.get("main_frequency") or ml.get("main_character"):
            st.markdown("#### Main light")
            if ml.get("main_light"):
                st.write("**Light index:**", ml["main_light"])
            if ml.get("main_colour"):
                st.write("**Main colour:**", ml["main_colour"])
            if ml.get("main_frequency"):
                st.write("**Main frequency:**", ml["main_frequency"])
            if ml.get("main_character"):
                st.write("**Character:**", ml["main_character"])

        sectors = parse_light_sectors(tags)
        if sectors:
            st.markdown("#### Sectors")
            st.dataframe(sectors, width="stretch", hide_index=True)
        else:
            st.caption("No sector data found in tags.")

        with st.expander("Raw JSON (lighthousedata.json)"):
            st.json(details)

    else:
        st.write("**Name:**", map_point.get("name", "Unnamed"))
        st.write("**ID:**", selected_id)
        st.write("**Lat/Lon:**", map_point.get("lat"), map_point.get("lon"))
        st.write("**Color:**", map_point.get("color"))
        st.write("**Sequence:**", map_point.get("sequence"))

        with st.expander("Raw JSON (map data)"):
            st.json(map_point)

st.divider()
colA, colB = st.columns([1, 4])
with colA:
    if st.button("Back to home"):
        st.switch_page("streamlit_app.py")
