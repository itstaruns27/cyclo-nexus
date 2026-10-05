"""
Collect NWP track guidance for every JTWC-numbered North Indian Ocean system since --since
═══════════════════════════════════════════════════════════════════════════════════════════
  python -m forecaster.guidance.build --since 2018 --threads 8

Writes data/guidance/guidance.csv.gz (one row per model/run/storm/member/lead time) and
data/guidance/storms.json (JTWC best-track truth). Raw downloads are cached in data/guidance/raw.
"""

import argparse
import gzip
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.guidance import sources as S  # noqa: E402

OUT = ROOT / "data" / "guidance"
RAW = OUT / "raw"
IBTRACS = ROOT / "data" / "static" / "ibtracs.NI.list.v04r01.csv"
SKIP_TECH = re.compile(r"^((AP|NP|CP|EP|UE|EE|E)\d\d|AC00|NC00|CC00|WRNG|CHI\w*|CHP\d|DSHP|SHIP|LGEM|SHF5|DRCL|CLP5|TCLP|XTRP|OFCL|OFCI)$")
FIELDS = ["model", "init", "atcf", "member", "tau", "lat", "lon", "vmax_kt", "pmin_hpa"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=2018)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()

    storms = S.ibtracs_storms(IBTRACS, since=args.since)
    print(f"{len(storms)} JTWC-numbered systems since {args.since}")
    rows = []

    # a-decks (GFS, GEFS mean, CMC, UKMET, NAVGEM …) — RAL publishes past seasons only
    def one_adeck(atcf):
        try:
            got = S.adeck(atcf, RAW) or []
        except Exception as e:  # noqa: BLE001
            print(f"  a-deck {atcf}: {e}")
            return []
        return [r for r in got if not SKIP_TECH.match(r["model"]) and r["atcf"] == atcf]

    with ThreadPoolExecutor(args.threads) as ex:
        for rs in ex.map(one_adeck, sorted(storms)):
            rows += rs
    print(f"a-decks: {len(rows)} rows")

    # ECMWF track BUFR for every synoptic run while a system existed (archive starts 18 Jan 2023)
    inits = sorted({t for s in storms.values() if s["season"] >= 2023 for t in S.synoptic_inits(s["fixes"])})
    print(f"ECMWF: {len(inits)} runs")
    n0, done = len(rows), 0
    with ThreadPoolExecutor(args.threads) as ex:
        futs = {ex.submit(S.ecmwf_run, t, RAW): t for t in inits}
        for f in as_completed(futs):
            done += 1
            try:
                rows += f.result()
            except Exception as e:  # noqa: BLE001
                print(f"  {futs[f]:%Y-%m-%d %HZ}: {e}")
            if done % 50 == 0:
                print(f"  {done}/{len(inits)} runs, {len(rows) - n0} rows")
    print(f"ECMWF: {len(rows) - n0} rows")

    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "guidance.csv.gz", "wt", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "init": r["init"].strftime("%Y-%m-%dT%H:%MZ")})
    (OUT / "storms.json").write_text(json.dumps({
        a: {**{k: v for k, v in s.items() if k != "fixes"},
            "fixes": [[t.strftime("%Y-%m-%dT%H:%MZ"), la, lo, None if w != w else w] for t, la, lo, w in s["fixes"]]}
        for a, s in storms.items()}, indent=0), encoding="utf-8")
    models = {}
    for r in rows:
        models[r["model"]] = models.get(r["model"], 0) + 1
    print("rows per model:", dict(sorted(models.items(), key=lambda kv: -kv[1])))
    print(f"built {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ}")


if __name__ == "__main__":
    main()
