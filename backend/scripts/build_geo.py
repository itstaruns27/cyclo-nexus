"""
Build the geographic layers used by Cyclo-Nexus
═══════════════════════════════════════════════
Inputs (data/static/geo/):
  ghs_pop_2020_30ss.zip                 GHS-POP R2023A, epoch 2020, 30 arc-second (~1 km) — EU JRC, CC-BY 4.0
  ne_10m_admin_0_countries_ind.geojson  Natural Earth 10m admin-0, India point of view (public domain):
                                        boundaries as officially recognised by the Government of India
Outputs:
  backend/data/pop_grid.bin + pop_grid.json   population per 2.5' cell (~4.6 km) over the NIO region,
                                              float32, row-major from the north-west corner
  backend/data/country_grid.bin               uint8 country index per cell (same grid, India view)
  frontend/public/geo/boundaries_in.geojson   simplified country outlines (India view) for the maps

  python backend/scripts/build_geo.py
"""

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data" / "static" / "geo"
POP_ZIP = GEO / "ghs_pop_2020_30ss.zip"
TIF = "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
NE = GEO / "ne_10m_admin_0_countries_ind.geojson"
OUT_BACK = ROOT / "backend" / "data"
OUT_FRONT = ROOT / "frontend" / "public" / "geo"

# Region (degrees) and aggregation: 5 × 30" = 2.5' cells
W, S, E, N = 40.0, -15.0, 110.0, 45.0
FACTOR = 5


def douglas_peucker(pts, tol):
    """Iterative Douglas–Peucker on an (n, 2) array; keeps the end points."""
    if len(pts) < 3:
        return pts
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        p, q = pts[a], pts[b]
        seg = pts[a + 1:b]
        d = q - p
        nrm = np.hypot(*d)
        dist = (np.abs(d[0] * (seg[:, 1] - p[1]) - d[1] * (seg[:, 0] - p[0])) / nrm) if nrm else np.hypot(*(seg - p).T)
        i = int(np.argmax(dist))
        if dist[i] > tol:
            keep[a + 1 + i] = True
            stack += [(a, a + 1 + i), (a + 1 + i, b)]
    return pts[keep]


def rings(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poly in polys:
        for ring in poly:
            yield np.asarray(ring, float)


def in_region(geom):
    for r in rings(geom):
        if r[:, 0].max() >= W and r[:, 0].min() <= E and r[:, 1].max() >= S and r[:, 1].min() <= N:
            return True
    return False


def main():
    countries = [f for f in json.loads(NE.read_text(encoding="utf-8"))["features"] if in_region(f["geometry"])]
    codes = [f["properties"].get("ISO_A2_EH") or f["properties"].get("ISO_A2") or f["properties"]["ADM0_A3"][:2]
             for f in countries]

    # ── Map outlines (India view), simplified ~2 km ──────────────────
    feats = []
    for f, cc in zip(countries, codes):
        lines = []
        for r in rings(f["geometry"]):
            s = douglas_peucker(r, 0.02)
            if len(s) >= 4:
                lines.append(np.round(s, 3).tolist())
        if lines:
            feats.append({"type": "Feature", "properties": {"iso": cc, "name": f["properties"]["NAME"]},
                          "geometry": {"type": "MultiLineString", "coordinates": lines}})
    OUT_FRONT.mkdir(parents=True, exist_ok=True)
    (OUT_FRONT / "boundaries_in.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "source": "Natural Earth 10m admin-0, India point of view (public domain); simplified by backend/scripts/build_geo.py",
        "features": feats}, separators=(",", ":")), encoding="utf-8")

    # ── Population grid ──────────────────────────────────────────────
    with rasterio.open(f"/vsizip/{POP_ZIP.as_posix()}/{TIF}") as src:
        win = from_bounds(W, S, E, N, src.transform).round_offsets().round_lengths()
        pop = src.read(1, window=win).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        pop[pop == nodata] = 0
    pop[pop < 0] = 0
    h, w = (pop.shape[0] // FACTOR) * FACTOR, (pop.shape[1] // FACTOR) * FACTOR
    pop = pop[:h, :w].reshape(h // FACTOR, FACTOR, w // FACTOR, FACTOR).sum(axis=(1, 3)).astype(np.float32)
    rows, cols = pop.shape
    cell = (E - W) / cols
    transform = from_origin(W, N, cell, cell)

    # ── Country per cell (India view) ────────────────────────────────
    shapes = [(f["geometry"], i + 1) for i, f in enumerate(countries)]
    cgrid = rasterize(shapes, out_shape=(rows, cols), transform=transform, fill=0, dtype="uint8", all_touched=False)

    OUT_BACK.mkdir(parents=True, exist_ok=True)
    pop.tofile(OUT_BACK / "pop_grid.bin")
    cgrid.tofile(OUT_BACK / "country_grid.bin")
    (OUT_BACK / "pop_grid.json").write_text(json.dumps({
        "source": "GHS-POP R2023A epoch 2020 (EU JRC, CC-BY 4.0), aggregated to 2.5 arc-minutes",
        "countries_source": "Natural Earth 10m admin-0, India point of view",
        "west": W, "north": N, "cell_deg": cell, "rows": rows, "cols": cols, "dtype": "float32",
        "countries": [""] + codes, "total_population": float(pop.sum())}, indent=1), encoding="utf-8")
    india = float(pop[cgrid == codes.index("IN") + 1].sum()) if "IN" in codes else 0
    print(f"grid {rows}x{cols} cells of {cell * 60:.1f}'; region population {pop.sum() / 1e9:.2f} bn; India {india / 1e9:.3f} bn; "
          f"{len(feats)} outlines → {OUT_FRONT / 'boundaries_in.geojson'}")


if __name__ == "__main__":
    main()
