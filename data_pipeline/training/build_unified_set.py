"""
Unified real-imagery training set — one download for detector, forecaster and intensity classifier
═══════════════════════════════════════════════════════════════════════════════════════════════════
Replaces the separate builders (build_training_set.py for YOLO, train_multi_horizon.py build for the
forecaster), which downloaded overlapping granules twice and stored float32 1024² frames (~10 MB each).

  1. Frame store  data/training/store/<granule>.npz   x: (4, 512, 512) uint8, ~0.5 MB
     Every INSAT granule is downloaded once (same workers and calibration as the live pipeline),
     block-averaged 1024² → 512² (≈ 10 km pixels; a cyclone spans 20–100 pixels) and quantised to
     uint8 exactly like the live transport. The 1024² float cache is deleted straight away.
  2. Windows      data/training/windows/<key>.npz     x: (6, 4, 256, 256) uint8 + multi-horizon labels
     For each chosen best-track point t: the live 6 × 3 h window ending at t. Points are taken as
     runs of consecutive 6-hourly fixes, so neighbouring windows share 4 of their 6 frames and each
     extra point costs only 2 downloads. Runs are spread over genesis / intensification / peak
     across storms so every intensity class is represented.
  3. Negatives    single frames at storm-free times (no NIO system within ±3 days).
  4. Frame labels data/training/frames.jsonl — written by `label`, for EVERY stored frame: all
     systems active at that time (IBTrACS 3-hourly rows, ±90 min), with position, wind, pressure
     and IMD grade. Detector boxes and intensity-class labels both come from this file.

  python -m data_pipeline.training.build_unified_set plan                     # counts, no download
  python -m data_pipeline.training.build_unified_set build --since 2018       # resumable
  python -m data_pipeline.training.build_unified_set label
Needs MOSDAC + Earthdata credentials in .env and an Indian IP (MOSDAC).
"""

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from data_pipeline.training.build_training_set import IBTRACS_NI, BBOX, utc, dataset_for  # noqa: E402

TRAIN = ROOT / "data" / "training"
STORE = TRAIN / "store"
WINDOWS = TRAIN / "windows"
WINDOW_INDEX = WINDOWS / "windows.jsonl"
NEG_INDEX = TRAIN / "negatives.jsonl"
FRAME_LABELS = TRAIN / "frames.jsonl"
RAW_CACHE = TRAIN / "_raw1024"          # transient float32 cache used by build_frame
STORE_SIZE = 512
WINDOW_SIZE = 256
SEQ_LEN, STEP_HOURS = 6, 3
LABEL_TOLERANCE = timedelta(minutes=90)
KMH_PER_KT = 1.852
ENV_PRESSURE = 1010.0
HORIZONS_H = (6, 12, 24, 48, 72)


def imd_grade(wind_kt):
    if wind_kt is None:
        return None
    kmh = wind_kt * KMH_PER_KT
    for limit, g in ((222, "SuCS"), (167, "ESCS"), (118, "VSCS"), (89, "SCS"), (62, "CS"), (50, "DD"), (31, "D")):
        if kmh >= limit:
            return g
    return "LPA"


# ── Best tracks ──────────────────────────────────────────────────────────

def read_tracks(since):
    """{sid: {time: row}} for every IBTrACS NI row (all hours) from season `since`."""
    tracks = {}
    for r in list(csv.DictReader(open(IBTRACS_NI, encoding="utf-8")))[1:]:
        if int(r["SEASON"]) < since - 1:
            continue
        wind = (r["NEWDELHI_WIND"].strip() or r["WMO_WIND"].strip())
        pres = (r["NEWDELHI_PRES"].strip() or r["WMO_PRES"].strip())
        tracks.setdefault(r["SID"], {})[utc(r["ISO_TIME"])] = {
            "sid": r["SID"], "name": r["NAME"], "season": int(r["SEASON"]), "basin": r["SUBBASIN"],
            "lat": float(r["LAT"]), "lon": float(r["LON"]),
            "wind_kt": float(wind) if wind else None, "pres_hpa": float(pres) if pres else None,
            "dist2land_km": float(r["DIST2LAND"] or 0),
            "grade_imd": r["NEWDELHI_GRADE"].strip() or None,
        }
    return tracks


def in_domain(row, margin=1.0):
    return (BBOX[0] + margin <= row["lat"] <= BBOX[1] - margin
            and BBOX[2] + margin <= row["lon"] <= BBOX[3] - margin)


def horizon_labels(track, t):
    row0 = track[t]
    y_track = np.zeros((len(HORIZONS_H), 2), np.float32)
    y_wind = np.zeros(len(HORIZONS_H), np.float32)
    y_dp = np.zeros(len(HORIZONS_H), np.float32)
    mask = np.zeros(len(HORIZONS_H), np.float32)
    for i, h in enumerate(HORIZONS_H):
        row = track.get(t + timedelta(hours=h))
        if not row or row["wind_kt"] is None or row["pres_hpa"] is None:
            continue
        y_track[i] = (row["lat"] - row0["lat"], row["lon"] - row0["lon"])
        y_wind[i] = row["wind_kt"]
        y_dp[i] = ENV_PRESSURE - row["pres_hpa"]
        mask[i] = 1.0
    return y_track, y_wind, y_dp, mask


def plan_windows(tracks, since, run_len, runs_per_storm):
    """Runs of consecutive 6-hourly ocean fixes; run position rotates through the storm life."""
    plan = []
    for sid, track in sorted(tracks.items()):
        fixes = [t for t, r in sorted(track.items())
                 if r["season"] >= since and t.hour % 6 == 0 and r["basin"] in ("BB", "AS")
                 and r["dist2land_km"] >= 50 and in_domain(r) and r["wind_kt"] is not None
                 and horizon_labels(track, t)[3][0] > 0]
        if not fixes:
            continue
        # consecutive (6 h apart) segments
        segs, cur = [], [fixes[0]]
        for t in fixes[1:]:
            if t - cur[-1] == timedelta(hours=6):
                cur.append(t)
            else:
                segs.append(cur)
                cur = [t]
        segs.append(cur)
        longest = max(segs, key=len)
        n = len(longest)
        peak_i = max(range(n), key=lambda i: track[longest[i]]["wind_kt"])
        peak_kt = track[longest[peak_i]]["wind_kt"]
        # Strong storms are rare in the NIO and matter most: longer run around their peak
        length = run_len * (2 if peak_kt * KMH_PER_KT >= 89 else 1)
        start = min(max(0, peak_i - length // 2), max(0, n - length))
        chosen = set(longest[start:start + length])
        # Named storms (≥ CS) also get an early-stage run: genesis and intensification
        if runs_per_storm > 1 and peak_kt * KMH_PER_KT >= 62 and start >= run_len:
            chosen |= set(longest[:run_len])
        plan += [(sid, t) for t in sorted(chosen)]
    return plan


def plan_negatives(tracks, since, n, seed=7):
    rng = random.Random(seed)
    storm_times = sorted(t for tr in tracks.values() for t in tr)
    start = datetime(max(since, 2016), 1, 1, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) - timedelta(days=3)
    out, tries = [], 0
    while len(out) < n and tries < n * 100:
        tries += 1
        t = start + timedelta(hours=6 * rng.randrange(int((end - start).total_seconds() // 21600)))
        if all(abs((t - s).total_seconds()) > 3 * 86400 for s in storm_times):
            out.append(t)
    return sorted(out)


# ── Frame store ──────────────────────────────────────────────────────────

def to_store(frame1024):
    k = frame1024.shape[-1] // STORE_SIZE
    small = frame1024.reshape(frame1024.shape[0], STORE_SIZE, k, STORE_SIZE, k).mean(axis=(2, 4))
    return (np.clip(small, 0, 1) * 255).round().astype(np.uint8)


def to_window(frame512_u8):
    k = frame512_u8.shape[-1] // WINDOW_SIZE
    x = frame512_u8.astype(np.float32).reshape(frame512_u8.shape[0], WINDOW_SIZE, k, WINDOW_SIZE, k).mean(axis=(2, 4))
    return x.round().astype(np.uint8)


class FrameStore:
    """Downloads each granule once; thread-safe. MOSDAC access is serialised (it is fast, ~3 s, and
    ISRO's server should not be hammered); the slow IMERG step (~50 s) runs in parallel threads,
    each with its own Earthdata session and cache directory."""

    def __init__(self, workers_for):
        import threading
        STORE.mkdir(parents=True, exist_ok=True)
        self.workers_for = workers_for
        self.mosdac_lock = threading.Lock()
        self.local = threading.local()
        self.count_lock = threading.Lock()
        self.downloads = 0

    def _thread_tools(self):
        if not hasattr(self.local, "gpm"):
            import threading
            from data_pipeline.ingestion.nasa_gpm_worker import NasaGpmIngestionWorker
            from data_pipeline.preprocessing.tensor_assembler import TensorAssembler
            self.local.gpm = NasaGpmIngestionWorker(cache_dir=TRAIN / "_gpm" / str(threading.get_ident()), keep_files=2)
            self.local.gpm.authenticate()
            self.local.assembler = TensorAssembler()
        return self.local.gpm, self.local.assembler

    def has(self, meta):
        return (STORE / f"{Path(meta['granule_id']).stem}.npz").exists()

    def build(self, meta):
        """Download + calibrate + store one granule (same steps as live_pipeline_runner.build_frame)."""
        from data_pipeline.ingestion.live_pipeline_runner import _fill_missing
        stem = Path(meta["granule_id"]).stem
        path = STORE / f"{stem}.npz"
        if path.exists():
            return stem
        gpm, assembler = self._thread_tools()
        insat = self.workers_for(meta["obs_time"])
        with self.mosdac_lock:
            raw = insat.download_granule(meta)
            ch = insat.extract_frame(raw, BBOX)
        g = gpm.fetch_latest(BBOX, before=meta["obs_time"] + timedelta(minutes=29))
        tir1 = _fill_missing(ch["TIR1"], float(np.nanmedian(ch["TIR1"])))
        tir2 = _fill_missing(ch["TIR2"], float(np.nanmedian(ch["TIR2"])))
        wv = _fill_missing(ch["WV"], float(np.nanmedian(ch["WV"])))
        rain = _fill_missing(g.precip, 0.0)
        frame = assembler.assemble_tensor(tir1, BBOX, tir2, BBOX, wv, BBOX, rain, BBOX)
        info = {"insat_granule": meta["granule_id"], "insat_time": meta["obs_time"].isoformat(),
                "gpm_granule": g.granule, "gpm_time": g.obs_time.isoformat()}
        tmp = path.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, x=to_store(frame), info=json.dumps(info))
        tmp.replace(path)
        with self.count_lock:
            self.downloads += 1
        return stem

    @staticmethod
    def load(stem):
        with np.load(STORE / f"{stem}.npz", allow_pickle=False) as z:
            return z["x"]


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_plan(args):
    tracks = read_tracks(args.since)
    plan = plan_windows(tracks, args.since, args.run_len, args.runs_per_storm)
    storms = {sid for sid, _ in plan}
    by_storm = {}
    for sid, t in plan:
        by_storm.setdefault(sid, []).append(t)
    # distinct 3-hourly frame times needed by all windows
    frame_times = {t - timedelta(hours=STEP_HOURS * k) for _, t in plan for k in range(SEQ_LEN)}
    n_frames = len(frame_times) + args.negatives
    grades = {}
    for sid, t in plan:
        g = imd_grade(tracks[sid][t]["wind_kt"])
        grades[g] = grades.get(g, 0) + 1
    print(f"storms {len(storms)} · windows {len(plan)} · frames to download ≈ {n_frames} "
          f"({len(frame_times)} window + {args.negatives} negative)")
    print(f"download ≈ {n_frames * 25 / 1024:.1f} GB (INSAT ~23 MB + IMERG ~2 MB per frame) · "
          f"kept on disk ≈ {n_frames * 0.55 / 1024 + len(plan) * 0.8 / 1024:.1f} GB")
    print("window intensity mix:", dict(sorted(grades.items(), key=lambda kv: -kv[1])))


def cmd_build(args):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from data_pipeline.ingestion.live_pipeline_runner import select_window, log
    from data_pipeline.ingestion.mosdac_worker import MosdacIngestionWorker

    tracks = read_tracks(args.since)
    plan = plan_windows(tracks, args.since, args.run_len, args.runs_per_storm)
    negs = plan_negatives(tracks, args.since, args.negatives)
    WINDOWS.mkdir(parents=True, exist_ok=True)
    read = lambda f: [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
    done = {r["key"] for r in read(WINDOW_INDEX) + read(NEG_INDEX)}
    log(f"plan: {len(plan)} windows + {len(negs)} negatives; {len(done)} already built")

    workers = {}

    def workers_for(t):
        ds = dataset_for(t)
        if ds not in workers:
            workers[ds] = MosdacIngestionWorker(dataset_id=ds, cache_dir=TRAIN / "_mosdac", keep_files=4)
            workers[ds].authenticate()
        return workers[ds]

    store = FrameStore(workers_for)

    # Phase 1 — granule lists (MOSDAC search only, sequential). Results are cached on disk so an
    # interrupted build resumes without repeating the searches.
    cache_path = TRAIN / "phase1_cache.jsonl"
    cached = {}
    if cache_path.exists():
        for l in cache_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                c = json.loads(l)
                cached[c["key"]] = [{**m, "obs_time": datetime.fromisoformat(m["obs_time"])} for m in c["window"]]                     if c["window"] else None

    def remember(key, window):
        with open(cache_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, "window": [{**m, "obs_time": m["obs_time"].isoformat()} for m in window]
                                 if window else None}) + "\n")

    jobs = []
    for sid, t in plan:
        key = f"{t:%Y%m%d%H}_{sid}"
        if key in done:
            continue
        if key in cached:
            window = cached[key]
        else:
            try:
                window = select_window(workers_for(t), at=t + timedelta(minutes=30))
                if len({m["granule_id"] for m in window}) < SEQ_LEN - 1:  # archive gaps: >1 frame repeated
                    log(f"{key}: skipped, window has archive gaps")
                    window = None
            except Exception as exc:
                log(f"{key}: no complete window ({exc})")
                window = None
            remember(key, window)
        if window:
            jobs.append(("win", key, sid, t, window))
    for t in negs:
        key = f"{t:%Y%m%d%H}_neg"
        if key in done:
            continue
        try:
            entries = workers_for(t).search_granules(start=t - timedelta(days=1), end=t, count=2000)
        except Exception as exc:
            log(f"{key}: search failed ({exc})")
            continue
        meta = min(entries, key=lambda e: abs(e["obs_time"] - t), default=None)
        if meta and abs(meta["obs_time"] - t) <= timedelta(minutes=45):
            jobs.append(("neg", key, None, t, [meta]))
    if args.max_jobs:
        jobs = jobs[:args.max_jobs]
    unique = {m["granule_id"]: m for *_, metas in jobs for m in metas if not store.has(m)}
    log(f"{len(jobs)} jobs need {len(unique)} new frames; downloading with {args.threads} threads")

    # Phase 2 — frames, in parallel
    failed = set()
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        futs = {pool.submit(store.build, m): gid for gid, m in unique.items()}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                f.result()
            except Exception as exc:
                failed.add(futs[f])
                log(f"{futs[f]}: failed ({exc})")
            if n % 10 == 0 or n == len(futs):
                log(f"frames {n}/{len(futs)} ({len(failed)} failed)")

    # Phase 3 — windows and negatives from the store
    built = 0
    for kind, key, sid, t, metas in jobs:
        if any(m["granule_id"] in failed or not store.has(m) for m in metas):
            continue
        stems = [Path(m["granule_id"]).stem for m in metas]
        if kind == "win":
            y_track, y_wind, y_dp, mask = horizon_labels(tracks[sid], t)
            np.savez_compressed(WINDOWS / f"{key}.npz", x=np.stack([to_window(store.load(s)) for s in stems]),
                                track=y_track, wind=y_wind, dp=y_dp, mask=mask)
            rec = {"key": key, "sid": sid, "season": tracks[sid][t]["season"], "time": t.isoformat(),
                   "frames": stems, "wind_kt": tracks[sid][t]["wind_kt"]}
            index = WINDOW_INDEX
        else:
            rec = {"key": key, "time": t.isoformat(), "frames": stems}
            index = NEG_INDEX
        with open(index, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        built += 1
    log(f"built {built} windows/negatives; {store.downloads} frames downloaded; {len(failed)} frames failed")
    for w in workers.values():
        w.logout()


def cmd_label(args):
    """Label every stored frame with all systems active at its time (detector + intensity classes)."""
    tracks = read_tracks(2000)
    rows_by_time = {}
    for tr in tracks.values():
        for t, r in tr.items():
            rows_by_time.setdefault(t, []).append(r)
    times = sorted(rows_by_time)
    import bisect
    out, n_pos = [], 0
    for path in sorted(STORE.glob("*.npz")):
        with np.load(path, allow_pickle=False) as z:
            info = json.loads(str(z["info"]))
        t = datetime.fromisoformat(info["insat_time"])
        i = bisect.bisect_left(times, t - LABEL_TOLERANCE)
        systems = {}
        while i < len(times) and times[i] <= t + LABEL_TOLERANCE:
            for r in rows_by_time[times[i]]:
                best = systems.get(r["sid"])
                if best is None or abs(times[i] - t) < best[0]:
                    systems[r["sid"]] = (abs(times[i] - t), r)
            i += 1
        objs = [{**r, "grade": imd_grade(r["wind_kt"]), "in_domain": in_domain(r, 0.0)}
                for _, r in systems.values()]
        objs = [o for o in objs if o["in_domain"]]
        n_pos += bool(objs)
        out.append({"frame": path.stem, "time": t.isoformat(), "season": t.year if t.month > 1 else t.year,
                    "systems": objs})
    FRAME_LABELS.write_text("\n".join(json.dumps(o) for o in out) + "\n", encoding="utf-8")
    print(f"{len(out)} frames labelled: {n_pos} with a system, {len(out) - n_pos} empty → {FRAME_LABELS}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "build"):
        p = sub.add_parser(name)
        p.add_argument("--since", type=int, default=2018)
        p.add_argument("--run-len", type=int, default=4, help="consecutive 6-hourly fixes per run")
        p.add_argument("--runs-per-storm", type=int, default=1)
        p.add_argument("--negatives", type=int, default=100)
        p.add_argument("--max-jobs", type=int, default=0)
        p.add_argument("--threads", type=int, default=8)
    sub.add_parser("label")
    args = ap.parse_args()
    {"plan": cmd_plan, "build": cmd_build, "label": cmd_label}[args.cmd](args)


if __name__ == "__main__":
    main()
