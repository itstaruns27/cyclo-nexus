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
    """Choose between INSAT-only, INSAT + global pre-trained model, and calibrated global model; validate; save."""
    import lightgbm as lgb
    df = pd.read_csv(FEATS)
    meta_cols = {"sid", "name", "season", "time", "frame", "jitter", "wind_kt", "dist2land_km"}
    base = [c for c in df.columns if c not in meta_cols]
    glob_info, gcols = None, None
    if HURSAT_FEATS.exists():
        gm, gcols, glob_info = fit_global()
        df["global_ir_kt"] = gm.predict(df[gcols])
    P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_child_samples=20, feature_fraction=0.7,
             bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=0)
    ROUNDS = 400

    def balanced(d):
        cls = d.wind_kt.map(imd_class)
        freq = cls.value_counts()
        return cls.map(lambda c: len(d) / (len(freq) * freq[c])).clip(upper=6).values

    def gbm(cols):
        def f(tr, te):
            m = lgb.train(P, lgb.Dataset(tr[cols], tr.wind_kt, weight=balanced(tr)), ROUNDS)
            return m.predict(te[cols])
        return f

    def linear(cols):
        def f(tr, te):
            A = np.c_[np.ones(len(tr)), tr[cols].fillna(tr[cols].median())]
            coef, *_ = np.linalg.lstsq(A, tr.wind_kt, rcond=None)
            return np.c_[np.ones(len(te)), te[cols].fillna(tr[cols].median())] @ coef
        return f

    variants = {"INSAT features (LightGBM)": gbm(base),
                "3-feature linear (Dvorak-like)": linear(["tb_ring_25_50", "eye_contrast", "cold213_100"])}
    if gcols:
        variants["INSAT + global pre-trained model (LightGBM)"] = gbm(base + ["global_ir_kt"])
        variants["Global model, calibrated to IMD (linear)"] = linear(["global_ir_kt"])

    def loso(fn, seasons):
        """Leave-one-season-out predictions (unjittered images) over `seasons`."""
        out = []
        for s in seasons:
            tr = df[(df.season != s) & df.season.isin(seasons)]
            te = df[(df.season == s) & (df.jitter == 0)]
            out.append(pd.DataFrame({"y": te.wind_kt.values, "p": fn(tr, te), "season": s}, index=te.index))
        return pd.concat(out)

    dev = [s for s in sorted(df.season.unique()) if s <= 2023]
    cv = {k: loso(fn, dev) for k, fn in variants.items()}
    cv_m = {k: metrics(v.y, v.p) for k, v in cv.items()}
    best = min((k for k in variants if "linear" not in k or "Global" in k), key=lambda k: cv_m[k]["rmse"])
    print("selection (LOSO 2018–23):", {k: round(v["rmse"], 1) for k, v in cv_m.items()}, "→", best)

    tr, te0 = df[df.season <= 2023], df[(df.season >= 2024) & (df.jitter == 0)]
    test = {k: metrics(te0.wind_kt, fn(tr, te0)) for k, fn in variants.items()}
    allcv = loso(variants[best], sorted(df.season.unique()))
    strong = allcv.y >= 64
    s_m = metrics(allcv.y[strong], allcv.p[strong])
    band = float(np.percentile(np.abs(allcv.p - allcv.y), 80))
    by_cls = []
    for i, c in enumerate(CLASSES):
        m = allcv.y.map(imd_class) == i
        if m.any():
            r = metrics(allcv.y[m], allcv.p[m])
            by_cls.append(f"| {c} | {r['n']} | {r['mae']:.1f} | {r['bias']:+.1f} | {100 * r['exact']:.0f}% | {100 * r['within1']:.0f}% |")
    conf = np.zeros((len(CLASSES), len(CLASSES)), int)
    for y, q in zip(allcv.y, allcv.p):
        conf[imd_class(y), imd_class(q)] += 1

    # Final model: chosen variant on every season (deployment)
    cols = base + (["global_ir_kt"] if "global" in best.lower() and "LightGBM" in best else [])
    if "linear" in best:
        cols = ["global_ir_kt"]
    final = lgb.train(P, lgb.Dataset(df[cols], df.wind_kt, weight=balanced(df)), ROUNDS)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    final.save_model(str(MODEL))
    tb = test[best]
    approved = bool(tb["rmse"] <= 12.0 and cv_m[best]["rmse"] < cv_m["3-feature linear (Dvorak-like)"]["rmse"])
    META.write_text(json.dumps({
        "features": cols, "global_features": gcols if "global_ir_kt" in cols else None, "variant": best,
        "trained": datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "train_seasons": "all (2018–2025) for deployment",
        "cv_2018_2023": cv_m[best], "test_2024_25": tb, "loso_all": metrics(allcv.y, allcv.p), "loso_strong": s_m,
        "error_band_kt_80": round(band, 1), "global": glob_info, "approved": approved,
        "labels": "IMD best-track 3-minute wind (IBTrACS NEWDELHI_WIND)",
    }, indent=1), encoding="utf-8")

    pct = lambda v: f"{100 * v:.0f}%"  # noqa: E731
    row = lambda k, m: f"| {k} | {m['rmse']:.1f} | {m['mae']:.1f} | {m['bias']:+.1f} | {pct(m['exact'])} | {pct(m['within1'])} |"  # noqa: E731
    head = ["| Method | RMSE (kt) | MAE (kt) | Bias (kt) | Exact IMD class | Within one class |", "|---|---|---|---|---|---|"]
    test_storms = ", ".join(sorted({f"{n.title()} {s}" for n, s in zip(te0.name, te0.season)}))
    lines = [
        "# Satellite intensity estimate — validation",
        "",
        f"Generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC by `python -m forecaster.intensity.train fit`.",
        "",
        "Estimates a storm's maximum sustained wind (IMD 3-minute, kt) and IMD class from the current INSAT image, the image",
        "3–9 h earlier and IMERG rain — an automated Dvorak-style analysis (eye auto-centring, cloud-top rings, cold-cloud cover).",
        "",
        f"**INSAT data:** {int((df.jitter == 0).sum())} images of {df.sid.nunique()} storms (2018–2025), IMD best-track labels.",
    ]
    if glob_info:
        lines += [f"**Global pre-training:** NOAA HURSAT-B1, {glob_info['storms']} storms worldwide 2004–2015, {glob_info['images']} "
                  f"images, JTWC/NHC 1-minute winds; on held-out storms RMSE {glob_info['holdout_rmse']:.1f} kt."]
    lines += [
        "",
        "## Model selection — leave-one-season-out, 2018–2023", "", *head, *[row(k, v) for k, v in cv_m.items()], "",
        f"Chosen: **{best}**.", "",
        f"## Test seasons 2024–25 (scored once; {len(te0)} images: {test_storms})", "", *head, *[row(k, v) for k, v in test.items()], "",
        "Note: 2024–25 had no storm above Severe Cyclonic Storm in IMD's best track, so the test is weak-storm heavy.",
        "",
        "## Every season, leave-one-season-out (chosen method) — includes Fani, Amphan, Tauktae, Mocha, Biparjoy",
        "", *head, row("All storms", metrics(allcv.y, allcv.p)), row("Storms ≥ 64 kt (VSCS+)", s_m), "",
        "| Class | Images | MAE (kt) | Bias (kt) | Exact | Within one |", "|---|---|---|---|---|---|", *by_cls, "",
        "Confusion matrix (rows = IMD best track, columns = estimate):", "",
        "| | " + " | ".join(CLASSES) + " |", "|---|" + "---|" * len(CLASSES),
        *[f"| {CLASSES[i]} | " + " | ".join(str(v) for v in conf[i]) + " |" for i in range(len(CLASSES))],
        "",
        f"80% of errors are within ±{band:.0f} kt — shown on the site as the estimate's range. Published geostationary-IR methods: "
        "RMSE ≈ 10–16 kt (Pradhan et al. 2018: 10.2 kt with many more storms). Plan target: RMSE ≤ 12 kt on 2024–25.",
        "",
        f"**Shown on the site: {'yes' if approved else 'no'}** (needs test RMSE ≤ 12 kt and beating the Dvorak-like baseline).",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


# ─── Global pre-training (HURSAT-B1) + stacking ────────────────────────────

HURSAT_FEATS = ROOT / "data" / "hursat" / "features.csv"
GLOBAL_MODEL = ROOT / "forecaster" / "weights" / "intensity_global_ir.txt"
NOT_IR = ("rain_", "d_rain_", "month_", "arabian_sea", "jitter")


def ir_cols(cols):
    return [c for c in cols if not c.startswith(NOT_IR)]


def fit_global(rounds=1500):
    """Infrared-only model on every HURSAT storm worldwide (JTWC/NHC 1-minute wind)."""
    import lightgbm as lgb
    h = pd.read_csv(HURSAT_FEATS)
    cols = ir_cols([c for c in h.columns if c not in ("sid", "time", "wind_kt", "lat")])
    p = dict(objective="regression", learning_rate=0.03, num_leaves=63, min_child_samples=40, feature_fraction=0.8,
             bagging_fraction=0.8, bagging_freq=1, lambda_l2=2.0, verbose=-1, seed=0)
    # hold out 20% of storms to report the global skill honestly
    sids = np.array(sorted(h.sid.unique()))
    rng = np.random.default_rng(0)
    hold = set(rng.choice(sids, size=len(sids) // 5, replace=False))
    tr, te = h[~h.sid.isin(hold)], h[h.sid.isin(hold)]
    m = lgb.train(p, lgb.Dataset(tr[cols], tr.wind_kt), rounds)
    e = m.predict(te[cols]) - te.wind_kt
    print(f"global IR model: {h.sid.nunique()} storms, {len(h)} images; held-out storms RMSE {np.sqrt((e ** 2).mean()):.1f} kt, "
          f"MAE {e.abs().mean():.1f}")
    final = lgb.train(p, lgb.Dataset(h[cols], h.wind_kt), rounds)
    final.save_model(str(GLOBAL_MODEL))
    return final, cols, {"storms": int(h.sid.nunique()), "images": int(len(h)),
                         "holdout_rmse": float(np.sqrt((e ** 2).mean())), "holdout_mae": float(e.abs().mean())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["features", "fit"])
    a = ap.parse_args()
    build_features() if a.cmd == "features" else fit()
