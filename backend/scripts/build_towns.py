"""
Build backend/data/geonames_nio.json (towns used by the impact engine) from GeoNames cities1000.
════════════════════════════════════════════════════════════════════════════════════════════════
Source: data/static/cities1000.zip (GeoNames, CC-BY 4.0) — every place with ≥ 1,000 people.

Avoiding double counting (a person must be counted once):
  - drop "section of populated place" (PPLX) entries: neighbourhoods such as Dharavi (Mumbai),
    Karol Bagh (Delhi) or Mirpur (Dhaka) are already inside their city's population;
    exception: Navi Mumbai, a separate planned city that GeoNames files as PPLX
  - drop historical / abandoned / destroyed places (PPLH, PPLQ, PPLW)
  - collapse large places (≥ 100,000) within 3 km of a larger one (e.g. Pimpri next to
    Pimpri-Chinchwad, Bawshar next to Muscat, Kanayannur next to Kochi)
  - DUPLICATES below: entries carrying a whole metro population under a suburb name

  python backend/scripts/build_towns.py
"""

import json
import math
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "static" / "cities1000.zip"
OUT = ROOT / "backend" / "data" / "geonames_nio.json"
BBOX = (-5.0, 35.0, 55.0, 105.0)   # lat min/max, lon min/max: North Indian Ocean rim
COUNTRIES = {"AE", "AF", "BD", "BT", "CN", "ID", "IN", "IR", "KH", "LA", "LK", "MM", "MV", "MY", "NP", "OM",
             "PK", "SC", "SG", "TH", "VN"}
SKIP_CODES = {"PPLX", "PPLH", "PPLQ", "PPLW"}
KEEP_PPLX = {"Navi Mumbai"}
DUPLICATES = {"Rasapūdipalem": "carries the Visakhapatnam metro population (Visakhapatnam itself is listed)"}


def km(a, b):
    r = math.pi / 180
    h = math.sin((b[1] - a[1]) * r / 2) ** 2 + math.cos(a[1] * r) * math.cos(b[1] * r) * math.sin((b[2] - a[2]) * r / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def main():
    rows, dropped = [], {"section": 0, "historical": 0, "duplicate": 0, "near-identical": 0}
    with zipfile.ZipFile(SRC) as z:
        for line in z.open("cities1000.txt"):
            f = line.decode("utf-8").rstrip("\n").split("\t")
            lat, lon, pop, code, cc, name = float(f[4]), float(f[5]), int(f[14] or 0), f[7], f[8], f[1]
            if not (BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lon <= BBOX[3]) or cc not in COUNTRIES or pop < 1000:
                continue
            if code in SKIP_CODES and name not in KEEP_PPLX:
                dropped["section" if code == "PPLX" else "historical"] += 1
                continue
            if name in DUPLICATES:
                dropped["duplicate"] += 1
                continue
            rows.append([name, round(lat, 3), round(lon, 3), pop, cc])

    rows.sort(key=lambda r: -r[3])
    big = [r for r in rows if r[3] >= 100_000]
    drop = set()
    for i, a in enumerate(big):
        if id(a) in drop:
            continue
        for b in big[i + 1:]:
            if id(b) not in drop and km(a, b) < 3:
                drop.add(id(b))
    dropped["near-identical"] = len(drop)
    rows = [r for r in rows if id(r) not in drop]

    OUT.write_text(json.dumps({
        "source": "GeoNames cities1000 (CC-BY 4.0); built by backend/scripts/build_towns.py",
        "fields": ["name", "lat", "lon", "population", "country"],
        "dropped": dropped, "rows": rows,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(rows)} towns → {OUT} (dropped {dropped})")


if __name__ == "__main__":
    main()
