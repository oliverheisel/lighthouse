import json
import gzip
import pandas as pd
from pathlib import Path

IN_JSON = Path("data/lighthousedata.json")
OUT_PARQUET = Path("data/lighthouses.parquet")
OUT_JSON_GZ = Path("server/site/data.min.json.gz")


def main():
    data = json.loads(IN_JSON.read_text(encoding="utf-8"))
    rows = []

    for el in data.get("elements", []):
        if el.get("type") != "node":
            continue
        if "lat" not in el or "lon" not in el:
            continue

        tags = el.get("tags") or {}

        if not (
            tags.get("man_made") == "lighthouse"
            or any(k.startswith("seamark:light") for k in tags)
        ):
            continue

        rows.append({
            "id": int(el["id"]),
            "lat": float(el["lat"]),
            "lon": float(el["lon"]),
            "name": (
                tags.get("name")
                or tags.get("seamark:name")
                or f"Lighthouse {el['id']}"
            ),
            "color": (
                tags.get("seamark:light:1:colour")
                or tags.get("seamark:light:colour")
                or ""
            ).lower(),
            "sequence": (
                tags.get("seamark:light:1:sequence")
                or tags.get("seamark:light:sequence")
                or ""
            ),
        })

    df = pd.DataFrame(rows).drop_duplicates("id")

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)

    OUT_JSON_GZ.parent.mkdir(parents=True, exist_ok=True)
    payload = df.to_dict(orient="records")

    with gzip.open(OUT_JSON_GZ, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Rows: {len(df)}")
    print(f"Wrote {OUT_PARQUET}")
    print(f"Wrote {OUT_JSON_GZ}")


if __name__ == "__main__":
    main()
