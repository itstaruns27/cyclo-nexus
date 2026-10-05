"""
ECMWF ensemble cyclone-genesis tracks for the North Indian Ocean (master plan v5, Task 3.4)
═════════════════════════════════════════════════════════════════════════════════════════
  python -m forecaster.genesis.build --since 2023-01-18 --workers 4

Every 00 and 12 UTC ECMWF ensemble run (IFS 51 members; AIFS ensemble when available) from the open-data
archive. The tropical-cyclone track files include tracks for vortices that do NOT exist yet — ECMWF's tracker
gives them IDs 70–79 (e.g. "71B"). Their spread across members is a forecast of cyclogenesis days ahead.

Writes data/genesis/ens_tracks.csv.gz: model, init, atcf (IOnnYYYY), member, tau, lat, lon, vmax_kt, pmin_hpa —
North Indian Ocean only, genesis IDs and numbered storms alike.
"""

import argparse
import csv
import gzip
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.guidance import sources as S  # noqa: E402

OUT = ROOT / "data" / "genesis"
FIELDS = ["model", "init", "atcf", "member", "tau", "lat", "lon", "vmax_kt", "pmin_hpa"]


def one_run(init_iso):
    init = datetime.fromisoformat(init_iso)
    try:
        return init_iso, S.ecmwf_run(init, ROOT / "data" / "guidance" / "raw", models=("IFS-ENS", "AIFS-ENS"))
    except Exception as e:  # noqa: BLE001
        return init_iso, e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2023-01-18")
    ap.add_argument("--until", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    t0 = datetime.fromisoformat(a.since).replace(tzinfo=timezone.utc)
    t1 = datetime.fromisoformat(a.until).replace(tzinfo=timezone.utc) if a.until else datetime.now(timezone.utc) - timedelta(hours=12)
    inits = []
    t = t0
    while t <= t1:
        inits.append(t)
        t += timedelta(hours=12)
    OUT.mkdir(parents=True, exist_ok=True)
    done_path = OUT / "done.txt"
    done = set(done_path.read_text().split()) if done_path.exists() else set()
    todo = [i.isoformat() for i in inits if i.isoformat() not in done]
    print(f"{len(inits)} runs, {len(todo)} to fetch", flush=True)
    path = OUT / "ens_tracks.csv.gz"
    new = not path.exists()
    n = 0
    with ProcessPoolExecutor(a.workers) as ex, gzip.open(path, "at", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        for fut in as_completed([ex.submit(one_run, i) for i in todo]):
            init_iso, rows = fut.result()
            if isinstance(rows, Exception):
                print(f"  {init_iso}: {rows}", flush=True)
                continue
            for r in rows:
                w.writerow({**r, "init": r["init"].strftime("%Y-%m-%dT%H:%MZ")})
            with open(done_path, "a") as d:
                d.write(init_iso + "\n")
            n += 1
            if n % 100 == 0:
                f.flush()
                print(f"  {n}/{len(todo)} runs", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
