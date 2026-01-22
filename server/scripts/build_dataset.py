import json
import gzip
from pathlib import Path
import pandas as pd

IN_JSON = Path("data/lighthousedata.json")
OUT_PARQUET = Path("data/lighthouses.parquet")
OUT_JSON = Path("server/site/data.min.json")
OUT_JSON_GZ = Path("server/site/data.min.json.gz")


def is_light_feature(tags: dict) -> bool:
    if not tags:
        return False
    if tags.get("man_made") == "lighthouse":
        return True
    if tags.get("building") == "lighthouse":
        return True
    return any(k.startswith("seamark:light") for k in tags.keys())


def pick_colour(tags: dict) -> str:
    c = (
        tags.get("seamark:light:1:colour")
        or tags.get("seamark:light:colour")
        or ""
    )
    return str(c).lower()


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
    return f"x{osm_id}"


def main():
    raw = IN_JSON.read_text(encoding="utf-8").strip()
    if not raw:
        raise RuntimeError("lighthousedata.json is empty")

    data = json.loads(raw)
    elements = data.get("elements", [])

    node_xy: dict[int, tuple[float, float]] = {}
    for el in elements:
        if el.get("type") == "node" and "lat" in el and "lon" in el:
            node_xy[int(el["id"])] = (float(el["lat"]), float(el["lon"]))

    rows = []
    seen = set()

    for el in elements:
        osm_type = el.get("type")
        osm_id = el.get("id")
        if osm_type not in ("node", "way") or osm_id is None:
            continue

        tags = el.get("tags") or {}
        if not is_light_feature(tags):
            continue

        lat = None
        lon = None

        if osm_type == "node":
            if "lat" not in el or "lon" not in el:
                continue
            lat = float(el["lat"])
            lon = float(el["lon"])

        if osm_type == "way":
            node_ids = el.get("nodes") or []
            pts = [node_xy.get(int(n)) for n in node_ids]
            pts = [p for p in pts if p is not None]
            if not pts:
                continue
            lat = sum(p[0] for p in pts) / len(pts)
            lon = sum(p[1] for p in pts) / len(pts)

        key = (osm_type, int(osm_id))
        if key in seen:
            continue
        seen.add(key)

        oid = int(osm_id)

        rows.append(
            {
                "key": make_key(osm_type, oid),
                "osm_type": osm_type,
                "osm_id": oid,
                "lat": lat,
                "lon": lon,
                "name": pick_name(tags, f"Lighthouse {osm_id}"),
                "color": pick_colour(tags),
                "sequence": pick_sequence(tags),
            }
        )

    df = pd.DataFrame(rows)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)

    payload = json.dumps(
        df.to_dict(orient="records"),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(payload, encoding="utf-8")

    with gzip.open(OUT_JSON_GZ, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(payload)

    print(f"Rows written: {len(df)}")
    print(df["osm_type"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
