"""
Satellite intensity estimator — build features, train, evaluate (master plan v5, Task 2.1)
═════════════════════════════════════════════════════════════════════════════════════════
  python -m forecaster.intensity.train features     # data/training/intensity_features.csv
  python -m forecaster.intensity.train fit           # model + docs/intensity_report.md

Labels: IMD (RSMC New Delhi) best-track 3-minute wind from IBTrACS, matched to every stored INSAT frame
(data/training/frames.jsonl). Split by season, no storm in two sets: train ≤ 2022, validation 2023
(model choices), test 2024–25 (scored once). The final model is refitted on ≤ 2023.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.intensity.features import sample_features  # noqa: E402
from forecaster.intensity.scale import imd_class, CLASSES  # noqa: E402

TRAIN = ROOT / "data" / "training"
FEATS = TRAIN / "intensity_features.csv"
MODEL = ROOT / "forecaster" / "weights" / "intensity_gbm.txt"
META = ROOT / "forecaster" / "weights" / "intensity_meta.json"
REPORT = ROOT / "docs" / "intensity_report.md"
JITTER_KM = 25          # live centres (official or detector) are off by ~10–40 km
N_JITTER = 2


def load_x(stem):
    return np.load(TRAIN / "store" / f"{stem}.npz")["x"]


def build_features():
    rows = [json.loads(line) for line in open(TRAIN / "frames.jsonl", encoding="utf-8")]
    by_sid = defaultdict(list)
    for r in rows:
        t = datetime.fromisoformat(r["time"])
        for s in r["systems"]:
            if s.get("in_domain") and s.get("wind_kt") is not None:
                by_sid[s["sid"]].append((t, r["frame"], s))
    rng = np.random.default_rng(0)
    out = []
    for sid, items in by_sid.items():
        items.sort(key=lambda it: it[0])
        for i, (t, stem, s) in enumerate(items):
            prev = None
            for tp, sp, ss in reversed(items[:i]):
                h = (t - tp).total_seconds() / 3600
                if 3 <= h <= 9:
                    prev = (sp, ss, h)
                    break
                if h > 9:
                    break
            x = load_x(stem)
            xp = load_x(prev[0]) if prev else None
            for j in range(1 + N_JITTER):
                dlat = dlon = 0.0
                if j:
                    ang, r = rng.uniform(0, 2 * np.pi), rng.uniform(0, JITTER_KM)
                    dlat = r * np.cos(ang) / 111.2
                    dlon = r * np.sin(ang) / (111.2 * np.cos(np.radians(s["lat"])))
                f = sample_features(x, s["lat"] + dlat, s["lon"] + dlon,
                                    xp, prev[1]["lat"] + dlat if prev else None, prev[1]["lon"] + dlon if prev else None,
                                    prev[2] if prev else None,
                                    extra={"month_sin": np.sin(2 * np.pi * t.month / 12), "month_cos": np.cos(2 * np.pi * t.month / 12),
                                           "arabian_sea": float(s["lon"] < 77.5 and s["lat"] > 5)})
                if f is None:
                    continue
                out.append({"sid": sid, "name": s["name"], "season": s["season"], "time": t.isoformat(), "frame": stem,
                            "jitter": j, "wind_kt": s["wind_kt"], "dist2land_km": s.get("dist2land_km"), **f})
        print(f"{sid} {items[0][2]['name']}: {len(items)} frames")
    df = pd.DataFrame(out)
    df.to_csv(FEATS, index=False)
    print(f"{len(df)} samples ({(df.jitter == 0).sum()} unjittered) from {df.sid.nunique()} storms → {FEATS}")


def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    cy, cp = np.array([imd_class(v) for v in y]), np.array([imd_class(v) for v in p])
    return {"n": int(len(y)), "rmse": float(np.sqrt(np.mean((p - y) ** 2))), "mae": float(np.mean(np.abs(p - y))),
            "bias": float(np.mean(p - y)), "exact": float(np.mean(cy == cp)), "within1": float(np.mean(np.abs(cy - cp) <= 1))}


def fit():
    import lightgbm as lgb
    df = pd.read_csv(FEATS)
    meta_cols = {"sid", "name", "season", "time", "frame", "jitter", "wind_kt", "dist2land_km"}
    cols = [c for c in df.columns if c not in meta_cols]
    tr, va, te = df[df.season <= 2022], df[df.season == 2023], df[df.season >= 2024]
    va0, te0 = va[va.jitter == 0], te[te.jitter == 0]
    # Inverse-frequency weights per IMD class so rare strong storms are not drowned by depressions
    def weights(d):
        cls = d.wind_kt.map(imd_class)
        freq = cls.value_counts()
        return cls.map(lambda c: len(d) / (len(freq) * freq[c])).clip(upper=6).values

    params = dict(objective="huber", alpha=12.0, learning_rate=0.03, num_leaves=15, min_child_samples=20,
                  feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=0)
    grid = []
    for nl in (7, 15, 31):
        for mcs in (10, 20, 40):
            for balanced in (False, True):
                p = {**params, "num_leaves": nl, "min_child_samples": mcs}
                m = lgb.train(p, lgb.Dataset(tr[cols], tr.wind_kt, weight=weights(tr) if balanced else None),
                              num_boost_round=3000, valid_sets=[lgb.Dataset(va0[cols], va0.wind_kt)],
                              callbacks=[lgb.early_stopping(150, verbose=False)])
                s = metrics(va0.wind_kt, m.predict(va0[cols], num_iteration=m.best_iteration))
                grid.append((s["rmse"], nl, mcs, balanced, m.best_iteration, s))
    grid.sort(key=lambda g: g[0])
    best_rmse, nl, mcs, balanced, iters, vs = grid[0]
    print(f"best on 2023: leaves {nl}, min child {mcs}, balanced {balanced}, {iters} rounds → RMSE {best_rmse:.1f} kt")

    # Baselines on the test seasons: climatology (train mean per month) and a 3-feature linear fit (Dvorak-like)
    clim = float(tr.wind_kt.mean())
    from numpy.linalg import lstsq
    lin_cols = ["tb_ring_25_50", "eye_contrast", "cold213_100"]
    A = np.c_[np.ones(len(tr)), tr[lin_cols].fillna(tr[lin_cols].median())]
    coef, *_ = lstsq(A, tr.wind_kt, rcond=None)
    lin = lambda d: np.c_[np.ones(len(d)), d[lin_cols].fillna(tr[lin_cols].median())] @ coef  # noqa: E731

    # Refit on ≤ 2023 with the chosen settings, fixed rounds (×1.1 for the extra season), test once
    full = df[df.season <= 2023]
    p = {**params, "num_leaves": nl, "min_child_samples": mcs}
    final = lgb.train(p, lgb.Dataset(full[cols], full.wind_kt, weight=weights(full) if balanced else None),
                      num_boost_round=int(iters * 1.1) + 1)
    pred = final.predict(te0[cols])
    ts = metrics(te0.wind_kt, pred)
    tc = metrics(te0.wind_kt, np.full(len(te0), clim))
    tl = metrics(te0.wind_kt, lin(te0))
    # Error by class and the 80% error interval (shown as the estimate's ± on the site)
    resid = pred - te0.wind_kt.values
    band = float(np.percentile(np.abs(resid), 80))
    by_cls = []
    for c in CLASSES:
        m = te0.wind_kt.map(imd_class) == CLASSES.index(c)
        if m.any():
            r = metrics(te0.wind_kt[m], pred[m.values])
            by_cls.append(f"| {c} | {r['n']} | {r['mae']:.1f} | {r['bias']:+.1f} | {100 * r['exact']:.0f}% |")
    conf = np.zeros((len(CLASSES), len(CLASSES)), int)
    for y, q in zip(te0.wind_kt, pred):
        conf[imd_class(y), imd_class(q)] += 1

    MODEL.parent.mkdir(parents=True, exist_ok=True)
    final.save_model(str(MODEL))
    imp = sorted(zip(cols, final.feature_importance("gain")), key=lambda kv: -kv[1])
    META.write_text(json.dumps({
        "features": cols, "trained": datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "train_seasons": "<= 2023",
        "test_seasons": ">= 2024", "test": ts, "error_band_kt_80": round(band, 1), "params": p,
        "labels": "IMD best-track 3-minute wind (IBTrACS NEWDELHI_WIND)",
    }, indent=1), encoding="utf-8")

    pct = lambda v: f"{100 * v:.0f}%"  # noqa: E731
    test_storms = ", ".join(sorted({f"{n.title()} {s}" for n, s in zip(te0.name, te0.season)}))
    lines = [
        "# Satellite intensity estimate — validation",
        "",
        f"Generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC by `python -m forecaster.intensity.train fit`.",
        "",
        "**What it does:** estimates a storm's maximum sustained wind (IMD 3-minute, knots) and its IMD class from one",
        "INSAT-3DR/3DS image (plus the image 3–9 h earlier when available) and IMERG rain — like an automated Dvorak analysis.",
        "",
        f"**Data:** {df[df.jitter == 0].shape[0]} storm images from {df.sid.nunique()} storms (2018–2025). Labels: IMD best track.",
        f"Train ≤ 2022 · choose settings on 2023 · **test 2024–25 ({len(te0)} images, never used before):** {test_storms}.",
        "",
        "## Test seasons 2024–25",
        "",
        "| Method | RMSE (kt) | MAE (kt) | Bias (kt) | Exact IMD class | Within one class |",
        "|---|---|---|---|---|---|",
        f"| **Cyclo-Nexus satellite estimate (LightGBM, {len(cols)} features)** | **{ts['rmse']:.1f}** | **{ts['mae']:.1f}** | {ts['bias']:+.1f} | **{pct(ts['exact'])}** | **{pct(ts['within1'])}** |",
        f"| 3-feature linear (Dvorak-like) | {tl['rmse']:.1f} | {tl['mae']:.1f} | {tl['bias']:+.1f} | {pct(tl['exact'])} | {pct(tl['within1'])} |",
        f"| Climatology (training mean {clim:.0f} kt) | {tc['rmse']:.1f} | {tc['mae']:.1f} | {tc['bias']:+.1f} | {pct(tc['exact'])} | {pct(tc['within1'])} |",
        "",
        f"Published research on geostationary IR: RMSE ≈ 10–16 kt (Pradhan et al. 2018: 10.2 kt; INSAT-3D CNN studies 10–16 kt). "
        f"Plan target: RMSE ≤ 12 kt, exact class ≥ 60%, within one class ≥ 90%. 80% of test errors are within ±{band:.0f} kt "
        "(shown on the site as the estimate's range).",
        "",
        "## By IMD class (test)",
        "",
        "| Class | Images | MAE (kt) | Bias (kt) | Exact class |", "|---|---|---|---|---|", *by_cls,
        "",
        "## Confusion matrix (rows = IMD best track, columns = estimate)",
        "",
        "| | " + " | ".join(CLASSES) + " |", "|---|" + "---|" * len(CLASSES),
        *[f"| {CLASSES[i]} | " + " | ".join(str(v) for v in conf[i]) + " |" for i in range(len(CLASSES))],
        "",
        f"## Validation season 2023 (settings chosen here): RMSE {vs['rmse']:.1f} kt, exact {pct(vs['exact'])}, within one {pct(vs['within1'])}",
        "",
        "## Most useful features",
        "",
        ", ".join(f"`{k}`" for k, _ in imp[:12]),
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["features", "fit"])
    a = ap.parse_args()
    build_features() if a.cmd == "features" else fit()
