import json
import gzip
from pathlib import Path

import pandas as pd

IN_JSON = Path("data/lighthousedata.json")

# Keep existing outputs unchanged
OUT_PARQUET = Path("data/lighthouses.parquet")
OUT_JSON = Path("server/site/data.min.json")
OUT_JSON_GZ = Path("server/site/data.min.json.gz")

# New enriched outputs
OUT_RICH_JSON = Path("server/site/data.rich.json")
OUT_RICH_JSON_GZ = Path("server/site/data.rich.json.gz")


def is_light_feature(tags: dict) -> bool:
    if not tags:
        return False
    if tags.get("man_made") == "lighthouse":
        return True
    if tags.get("building") == "lighthouse":
        return True
    return any(str(k).startswith("seamark:light") for k in tags.keys())


def pick_colour(tags: dict) -> str:
    return str(
        tags.get("seamark:light:1:colour")
        or tags.get("seamark:light:colour")
        or ""
    ).lower()


def pick_sequence(tags: dict) -> str:
    return (
        tags.get("seamark:light:1:sequence")
        or tags.get("seamark:light:sequence")
        or ""
    )


def pick_name(tags: dict, fallback: str) -> str:
    return tags.get("name") or tags.get("seamark:name") or fallback


def make_key(osm_type: str, osm_id: int) -> str:
    if osm_type == "node":
        return f"n{osm_id}"
    if osm_type == "way":
        return f"w{osm_id}"
    if osm_type == "relation":
        return f"r{osm_id}"
    return f"x{osm_id}"


def parse_float(x) -> float | None:
    if x is None:
        return None
    s = str(x).strip().lower()
    if not s:
        return None
    s = s.replace("s", "").strip()
    try:
        return float(s)
    except Exception:
        return None


def has_unindexed_light(tags: dict) -> bool:
    # seamark:light:colour, seamark:light:period etc, but not seamark:light:<n>:...
    for k in (tags or {}).keys():
        ks = str(k)
        if ks.startswith("seamark:light:") and ":1:" not in ks and ":2:" not in ks and ":3:" not in ks:
            # This is a cheap check, the proper check is "seamark:light:<n>:"
            # We treat any non-indexed key under seamark:light: as unindexed.
            # Example: seamark:light:colour
            parts = ks.split(":")
            if len(parts) == 3:
                return True
    return False


def indexed_keys(tags: dict) -> set[int]:
    idxs = set()
    for k in (tags or {}).keys():
        ks = str(k)
        if not ks.startswith("seamark:light:"):
            continue
        parts = ks.split(":")
        if len(parts) < 4:
            continue
        # seamark:light:<n>:field
        try:
            idx = int(parts[2])
            idxs.add(idx)
        except Exception:
            pass
    return idxs


def first_light_index(tags: dict) -> int | None:
    if not isinstance(tags, dict):
        return None
    if has_unindexed_light(tags):
        return 0

    idxs = indexed_keys(tags)
    if idxs:
        return min(idxs)

    # Some datasets only include :1: keys but our scan missed them due to formatting
    if any(str(k).startswith("seamark:light:1:") for k in tags.keys()):
        return 1

    return None


def main_light_fields(tags: dict) -> dict:
    idx = first_light_index(tags)
    if idx is None:
        return {
            "main_colour": "",
            "main_period": None,
            "main_character": "",
            "main_sequence": "",
        }

    if idx == 0:
        character = tags.get("seamark:light:character", "") or ""
        colour = tags.get("seamark:light:colour", "") or ""
        period = parse_float(tags.get("seamark:light:period", ""))
        sequence = tags.get("seamark:light:sequence", "") or ""
        return {
            "main_colour": str(colour).lower(),
            "main_period": period,
            "main_character": str(character),
            "main_sequence": str(sequence),
        }

    base = f"seamark:light:{idx}:"
    character = tags.get(base + "character", "") or ""
    colour = tags.get(base + "colour", "") or ""
    period = parse_float(tags.get(base + "period", ""))
    sequence = tags.get(base + "sequence", "") or ""
    return {
        "main_colour": str(colour).lower(),
        "main_period": period,
        "main_character": str(character),
        "main_sequence": str(sequence),
    }


def parse_sectors(tags: dict, limit: int = 5) -> list[dict]:
    """
    Returns compact sector list:
      { "ss": <start_deg>, "se": <end_deg>, "c": <colour>, "q": <sequence>, "p": <period>, "ch": <character> }
    Values are strings where input is not numeric.
    """
    if not isinstance(tags, dict):
        return []

    # Collect per index
    sectors: dict[int, dict] = {}
    for k, v in tags.items():
        ks = str(k)
        if not ks.startswith("seamark:light:"):
            continue
        parts = ks.split(":")
        if len(parts) < 4:
            continue
        # seamark:light:<idx>:<field>
        try:
            idx = int(parts[2])
        except Exception:
            continue
        field = ":".join(parts[3:])
        sectors.setdefault(idx, {})[field] = v

    if not sectors:
        return []

    out = []
    for idx in sorted(sectors.keys()):
        s = sectors[idx]
        ss = s.get("sector_start", "")
        se = s.get("sector_end", "")
        c = str(s.get("colour", "") or "").lower()
        q = str(s.get("sequence", "") or "")
        p = parse_float(s.get("period", ""))
        ch = str(s.get("character", "") or "")
        out.append({"ss": ss, "se": se, "c": c, "q": q, "p": p, "ch": ch})

        if len(out) >= limit:
            break

    return out


def compute_lat_lon(el: dict, node_xy: dict[int, tuple[float, float]]) -> tuple[float, float] | None:
    osm_type = el.get("type")
    if osm_type == "node":
        if "lat" not in el or "lon" not in el:
            return None
        return float(el["lat"]), float(el["lon"])

    if osm_type == "way":
        node_ids = el.get("nodes") or []
        pts = [node_xy.get(int(n)) for n in node_ids]
        pts = [p for p in pts if p is not None]
        if not pts:
            return None
        lat = sum(p[0] for p in pts) / len(pts)
        lon = sum(p[1] for p in pts) / len(pts)
        return float(lat), float(lon)

    return None


def write_json_minified(path: Path, obj) -> str:
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return payload


def write_gzip_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(text)


def main():
    raw = IN_JSON.read_text(encoding="utf-8").strip()
    if not raw:
        raise RuntimeError("data/lighthousedata.json is empty")

    data = json.loads(raw)
    elements = data.get("elements", [])
    if not isinstance(elements, list):
        raise RuntimeError("Expected dict with key 'elements' being a list")

    # Node index for way centroid calc
    node_xy: dict[int, tuple[float, float]] = {}
    for el in elements:
        if el.get("type") == "node" and "lat" in el and "lon" in el and el.get("id") is not None:
            node_xy[int(el["id"])] = (float(el["lat"]), float(el["lon"]))

    seen = set()
    rows_min = []
    rows_rich = []

    for el in elements:
        osm_type = el.get("type")
        osm_id = el.get("id")
        if osm_type not in ("node", "way", "relation") or osm_id is None:
            continue

        tags = el.get("tags") or {}
        if not is_light_feature(tags):
            continue

        ll = compute_lat_lon(el, node_xy)
        if not ll:
            continue
        lat, lon = ll

        key_tuple = (osm_type, int(osm_id))
        if key_tuple in seen:
            continue
        seen.add(key_tuple)

        oid = int(osm_id)
        key = make_key(osm_type, oid)

        name = pick_name(tags, f"Lighthouse {oid}")
        color = pick_colour(tags)
        sequence = pick_sequence(tags)

        # Minimal row (keep identical schema as before)
        rows_min.append(
            {
                "key": key,
                "osm_type": osm_type,
                "osm_id": oid,
                "lat": lat,
                "lon": lon,
                "name": name,
                "color": color,
                "sequence": sequence,
            }
        )

        # Rich row
        ml = main_light_fields(tags)
        sectors = parse_sectors(tags, limit=5)

        rows_rich.append(
            {
                "key": key,
                "osm_type": osm_type,
                "osm_id": oid,
                "lat": lat,
                "lon": lon,
                "name": name,
                "color": color,
                "sequence": sequence,
                "main_colour": ml.get("main_colour", ""),
                "main_period": ml.get("main_period", None),
                "main_character": ml.get("main_character", ""),
                "main_sequence": ml.get("main_sequence", ""),
                "sectors": sectors,
            }
        )

    # Parquet stays useful for analysis and is optional for GitHub Pages
    df = pd.DataFrame(rows_min)
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)

    # Write minimal JSON and gzip (unchanged fields)
    payload_min = write_json_minified(OUT_JSON, rows_min)
    write_gzip_text(OUT_JSON_GZ, payload_min)

    # Write rich JSON and gzip
    payload_rich = write_json_minified(OUT_RICH_JSON, rows_rich)
    write_gzip_text(OUT_RICH_JSON_GZ, payload_rich)

    print(f"Rows written (min):  {len(rows_min)} -> {OUT_JSON}")
    print(f"Rows written (rich): {len(rows_rich)} -> {OUT_RICH_JSON}")

    if not df.empty and "osm_type" in df.columns:
        print(df["osm_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
