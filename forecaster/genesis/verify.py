"""
Cyclogenesis alerts from the ECMWF ensemble — fit on 2023–24, test on 2025–26 (master plan v5, Task 3.4)
════════════════════════════════════════════════════════════════════════════════════════════════════════
  python -m forecaster.genesis.verify

Alert rule (per ensemble run):
  1. genesis point of a member = first lead ≤ H where a NEW vortex (ECMWF tracker IDs 70–79, or a not-yet-numbered
     invest 90–99) reaches ≥ V kt 10-m wind for two consecutive 6-h steps;
  2. probability map on a 1° grid = share of members with a genesis point within 300 km;
  3. alerts = peaks with probability ≥ p (suppressing 600 km around each), issued when the run's files are published
     (init + 8 h).
An alert is a HIT if IMD declares a Depression within 500 km between its issue time and init + H + 24 h;
alerts near a system IMD already declared in the last 72 h are ignored (not genesis); others are FALSE ALARMS.
Lead time = IMD Depression time − issue time of the first hit alert. JTWC's invest designation is the benchmark.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.genesis import truth as T  # noqa: E402
from forecaster.guidance.sources import great_circle_km  # noqa: E402

DATA = ROOT / "data" / "genesis"
REPORT = ROOT / "docs" / "genesis_report.md"
SETTINGS = ROOT / "forecaster" / "weights" / "genesis.json"
ISSUE_DELAY = timedelta(hours=8)
GRID_LAT = np.arange(0.5, 30.5, 1.0)
GRID_LON = np.arange(40.5, 100.5, 1.0)
R_KM, SUPPRESS_KM, MATCH_KM = 300.0, 600.0, 500.0


def load_tracks(model="IFS-ENS"):
    g = pd.read_csv(DATA / "ens_tracks.csv.gz")
    g = g[(g.model == model)]
    g["num"] = g.atcf.str[2:4].astype(int)
    g = g[g.num >= 70]                                            # new vortices + invests, not numbered storms
    g["init"] = pd.to_datetime(g.init, utc=True)
    g["lon"] = ((g.lon + 180) % 360) - 180
    return g.sort_values(["init", "atcf", "member", "tau"])


def members_per_run(model="IFS-ENS"):
    g = pd.read_csv(DATA / "ens_tracks.csv.gz", usecols=["model", "init", "member"])
    g = g[g.model == model]
    g["init"] = pd.to_datetime(g.init, utc=True)
    return g.groupby("init").member.nunique().to_dict()


def genesis_points(g, v_kt, h_max):
    """{init: [(member, lat, lon, tau)]} — first two-step ≥ v_kt point of each member track within h_max."""
    out = defaultdict(list)
    for (init, atcf, member), tr in g.groupby(["init", "atcf", "member"], sort=False):
        tr = tr[(tr.tau <= h_max) & (tr.lat > 0) & (tr.lat < 30) & (tr.lon > 40) & (tr.lon < 100)]
        v = tr.vmax_kt.to_numpy()
        ok = (v[:-1] >= v_kt) & (v[1:] >= v_kt) if len(v) > 1 else np.array([], bool)
        if ok.any():
            k = int(np.argmax(ok))
            r = tr.iloc[k]
            out[init].append((member, float(r.lat), float(r.lon), int(r.tau)))
    return out


def alerts_for(points, n_members, p_min):
    """[(lat, lon, prob, median genesis lead h)] for one run."""
    if not points or not n_members:
        return []
    la = np.array([p[1] for p in points])
    lo = np.array([p[2] for p in points])
    mem = np.array([p[0] for p in points])
    tau = np.array([p[3] for p in points])
    prob = np.zeros((len(GRID_LAT), len(GRID_LON)))
    for i, gl in enumerate(GRID_LAT):
        d = great_circle_km(gl, GRID_LON[:, None], la[None, :], lo[None, :])     # (lon, points)
        for j in range(len(GRID_LON)):
            prob[i, j] = len(set(mem[d[j] <= R_KM])) / n_members
    out = []
    while True:
        i, j = np.unravel_index(int(np.argmax(prob)), prob.shape)
        if prob[i, j] < p_min:
            break
        near = great_circle_km(GRID_LAT[i], GRID_LON[j], la, lo) <= R_KM
        out.append((float(GRID_LAT[i]), float(GRID_LON[j]), float(prob[i, j]), float(np.median(tau[near]))))
        for ii, gl in enumerate(GRID_LAT):
            prob[ii, great_circle_km(gl, GRID_LON, GRID_LAT[i], GRID_LON[j]) <= SUPPRESS_KM] = 0
    return out


def score(pts, nmem, events, p_min, h_max, t0, t1):
    """Hits / misses / false alarms and lead times for runs with t0 ≤ init < t1 and events in the same window."""
    evs = [e for e in events if t0 + ISSUE_DELAY <= e["t_imd"] < t1 + timedelta(hours=h_max)]
    first_hit = {}
    false, total = 0, 0
    false_list = []
    for init in sorted(i for i in nmem if t0 <= i < t1):
        issue = init + ISSUE_DELAY
        for lat, lon, p, _ in alerts_for(pts.get(init, []), nmem[init], p_min):
            close = [e for e in events if great_circle_km(lat, lon, e["lat"], e["lon"]) <= MATCH_KM]
            if any(issue - timedelta(hours=72) <= e["t_imd"] < issue for e in close):
                continue                                              # an existing system, not genesis
            total += 1
            hit = [e for e in close if issue <= e["t_imd"] <= init + timedelta(hours=h_max + 24)]
            if hit:
                for e in hit:
                    first_hit.setdefault(e["sid"], issue)
            else:
                false += 1
                false_list.append((init, lat, lon, p))
    leads = {e["sid"]: (e["t_imd"] - first_hit[e["sid"]]).total_seconds() / 3600 for e in evs if e["sid"] in first_hit}
    hits = len(leads)
    misses = len(evs) - hits
    return {"events": len(evs), "hits": hits, "misses": misses, "alerts": total, "false": false,
            "pod": hits / max(1, len(evs)), "far": false / max(1, total), "csi": hits / max(1, hits + misses + false),
            "leads": leads, "false_list": false_list}


def main():
    events = T.with_invest_times(T.events(2023), T.invest_fixes([2023, 2024, 2025, 2026]))
    g = load_tracks()
    nmem = members_per_run()
    utc = lambda y, m=1, d=1: datetime(y, m, d, tzinfo=timezone.utc)  # noqa: E731
    dev, test = (utc(2023, 1, 18), utc(2025)), (utc(2025), utc(2027))
    cache, grid = {}, []
    for v in (17, 20, 25, 30):
        for h in (72, 120, 168):
            cache[(v, h)] = genesis_points(g, v, h)
            for p in (0.1, 0.2, 0.3, 0.4, 0.5):
                s = score(cache[(v, h)], nmem, events, p, h, *dev)
                grid.append((s["csi"], v, h, p, s))
                print(f"V {v} H {h} p {p}: POD {s['pod']:.2f} FAR {s['far']:.2f} CSI {s['csi']:.2f} "
                      f"median lead {np.median(list(s['leads'].values())) if s['leads'] else float('nan'):.0f} h", flush=True)
    grid.sort(key=lambda r: -r[0])
    _, v, h, p, sdev = grid[0]
    st = score(cache[(v, h)], nmem, events, p, h, *test)

    def table(s, label):
        lines = [f"### {label}", "",
                 f"Depressions: {s['events']} · found before IMD declared them: **{s['hits']} ({100 * s['pod']:.0f}%)** · "
                 f"alerts {s['alerts']}, false {s['false']} (**FAR {100 * s['far']:.0f}%**) · CSI {s['csi']:.2f}", "",
                 "| System | IMD Depression | Peak | Our first alert: lead (h) | JTWC invest: lead (h) |", "|---|---|---|---|---|"]
        win = [e for e in events if any(e["sid"] == k for k in s["leads"]) or
               (label.startswith("Test") and e["t_imd"] >= test[0]) or (label.startswith("Fit") and dev[0] <= e["t_imd"] < dev[1])]
        for e in sorted(win, key=lambda e: e["t_imd"]):
            ours = s["leads"].get(e["sid"])
            inv = (e["t_imd"] - e["t_invest"]).total_seconds() / 3600 if e.get("t_invest") else None
            lines.append(f"| {e['name'].title()} | {e['t_imd']:%Y-%m-%d %H}Z | {e['peak_grade'] or '—'} | "
                         f"{'**%.0f**' % ours if ours is not None else 'missed'} | {'%.0f' % inv if inv is not None else '—'} |")
        both = [(s["leads"][e["sid"]], (e["t_imd"] - e["t_invest"]).total_seconds() / 3600) for e in win
                if e["sid"] in s["leads"] and e.get("t_invest")]
        if both:
            lines += ["", f"Where both exist ({len(both)} systems): median lead **{np.median([a for a, _ in both]):.0f} h** "
                      f"(ours) vs {np.median([b for _, b in both]):.0f} h (JTWC invest); ours earlier in "
                      f"{sum(a > b for a, b in both)} of {len(both)}."]
        named = [e for e in win if e["peak_grade"] in ("CS", "SCS", "VSCS", "ESCS", "SUCS", "SuCS")]
        if named:
            nh = [e for e in named if e["sid"] in s["leads"]]
            lines += [f"Named cyclones (CS and stronger): {len(nh)} of {len(named)} found, median lead "
                      f"{np.median([s['leads'][e['sid']] for e in nh]) if nh else float('nan'):.0f} h."]
        return lines

    report = [
        "# Cyclogenesis alerts (ECMWF ensemble) — verification",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m forecaster.genesis.verify`.",
        "",
        "**Data:** every 00/12 UTC ECMWF ensemble run since 18 Jan 2023 (51 members, open data, tropical-cyclone track files).",
        "**Truth:** IMD best-track time when each North Indian Ocean system was first graded a Depression (IBTrACS).",
        "**Benchmark:** JTWC's first invest designation (UCAR RAL ATCF archive). IMD's own lead is 0 h by definition.",
        "Alert lead times count from when the run is published (init + 8 h), so they are achievable in real time.",
        "",
        f"**Settings chosen on 2023–24 (best CSI):** vortex ≥ {v} kt for 12 h within {h} h, probability ≥ {int(p * 100)}%.",
        "",
        *table(sdev, "Fit seasons 2023–24"),
        "",
        *table(st, "Test seasons 2025–26 (never used to choose settings)"),
        "",
        "False alarms in the test seasons (run, place, probability): "
        + "; ".join(f"{i:%Y-%m-%d %H}Z {la:.0f}N {lo:.0f}E {100 * pp:.0f}%" for i, la, lo, pp in st["false_list"][:15])
        + (" …" if len(st["false_list"]) > 15 else ""),
        "",
    ]
    REPORT.write_text("\n".join(report), encoding="utf-8")
    SETTINGS.write_text(json.dumps({"vortex_kt": v, "max_lead_h": h, "min_prob": p, "radius_km": R_KM,
                                    "issue_delay_h": 8, "test": {k: st[k] for k in ("events", "hits", "alerts", "false", "pod", "far", "csi")},
                                    "test_median_lead_h": float(np.median(list(st["leads"].values()))) if st["leads"] else None,
                                    "trained": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}, indent=1), encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
