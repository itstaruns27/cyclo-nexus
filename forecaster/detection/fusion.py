"""
Detector fusion: one calibrated "watch probability" per candidate (master plan v5, Task 3.3)
═════════════════════════════════════════════════════════════════════════════════════════════
  python -m forecaster.detection.fusion

Gradient-boosted classifier on leak-free candidate descriptors (data/training/candidates.csv): physics detector
measurements + Dvorak-style ring/eye features + the global (HURSAT-trained) infrared intensity estimate +
latitude/season. Validated leave-one-season-out 2018–2025 (each season scored by a model that never saw it).

Frame-level scores, as the public sees them:
  found       a best-track system has a candidate ≥ threshold within 300 km of its centre
  false alarm a frame has a candidate ≥ threshold more than 500 km from every best-track system
  centre error distance from the best candidate to the best-track centre
Baselines on the same frames: the live physics rule (passes and score ≥ 0.95) and YOLO-OBB (2024–25 only:
YOLO was trained on 2018–22 and tuned on 2023).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

TRAIN = ROOT / "data" / "training"
MODEL = ROOT / "forecaster" / "weights" / "watch_fusion.txt"
META = ROOT / "forecaster" / "weights" / "watch_fusion.json"
REPORT = ROOT / "docs" / "detection_report.md"
NOT_FEATURES = {"frame", "time", "season", "source", "lat", "lon", "dist_km", "label", "sys_sid", "sys_wind_kt",
                "yolo_conf", "n_hist", "jitter"}
PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_child_samples=20, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=2.0, verbose=-1, seed=0)
ROUNDS = 400


def frame_scores(df, score_col, thr, frames_systems):
    """found / systems, false-alarm frames / frames, median centre error (km) of found systems."""
    found = tot = fa_frames = 0
    errs = []
    for frame, systems in frames_systems.items():
        c = df[(df.frame == frame) & (df[score_col] >= thr)]
        if (c.dist_km > 500).any():
            fa_frames += 1
        for sid in systems:
            tot += 1
            m = c[(c.sys_sid == sid) & (c.dist_km <= 300)]
            if len(m):
                found += 1
                errs.append(float(m.sort_values(score_col, ascending=False).dist_km.iloc[0]))
    n = len(frames_systems)
    return {"found": found, "systems": tot, "pod": found / max(1, tot), "fa_frames": fa_frames, "frames": n,
            "fa_rate": fa_frames / max(1, n), "median_err_km": float(np.median(errs)) if errs else float("nan")}


def main():
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score
    df = pd.read_csv(TRAIN / "candidates.csv")
    df["is_yolo"] = (df.source == "yolo").astype(int)
    cols = [c for c in df.columns if c not in NOT_FEATURES and c != "source"]
    frames = json.loads("[" + ",".join(open(TRAIN / "frames.jsonl", encoding="utf-8").read().split("\n")[:-1]) + "]")
    systems = {r["frame"]: [s["sid"] for s in r["systems"] if s.get("in_domain") and s.get("wind_kt") is not None]
               for r in frames}
    season_of = {r["frame"]: r["season"] for r in frames}

    df["p"] = np.nan
    for s in sorted(df.season.unique()):
        tr, te = df[df.season != s], df[df.season == s]
        m = lgb.train(PARAMS, lgb.Dataset(tr[cols], tr.label), ROUNDS)
        df.loc[te.index, "p"] = m.predict(te[cols])
    auc = roc_auc_score(df.label, df.p)
    df["physics_rule"] = ((df.phys_passes == 1) & (df.phys_score >= 0.95)).astype(float)

    allf = {f: systems[f] for f in systems}
    test_f = {f: v for f, v in systems.items() if season_of[f] >= 2024}
    # threshold: highest found-rate with ≤ 5% false-alarm frames (plan target), chosen on 2018–23 out-of-fold scores
    dev_f = {f: v for f, v in systems.items() if season_of[f] <= 2023}
    sweep = [(t, frame_scores(df, "p", t, dev_f)) for t in np.round(np.arange(0.2, 0.96, 0.05), 2)]
    ok = [(t, s) for t, s in sweep if s["fa_rate"] <= 0.05]
    thr = max(ok, key=lambda ts: ts[1]["pod"])[0] if ok else 0.9

    rows = {
        "Cyclo-Nexus fusion (this model)": ("p", thr),
        "Physics detector, live rule (score ≥ 0.95)": ("physics_rule", 1.0),
    }
    res_all = {k: frame_scores(df, c, t, allf) for k, (c, t) in rows.items()}
    res_test = {k: frame_scores(df, c, t, test_f) for k, (c, t) in rows.items()}
    for conf in (0.5, 0.7):
        res_test[f"YOLO-OBB alone (confidence ≥ {conf})"] = frame_scores(df[df.is_yolo == 1].assign(yc=lambda d: d.yolo_conf), "yc", conf, test_f)

    final = lgb.train(PARAMS, lgb.Dataset(df[cols], df.label), ROUNDS)
    final.save_model(str(MODEL))
    imp = sorted(zip(cols, final.feature_importance("gain")), key=lambda kv: -kv[1])[:12]
    passed = res_test["Cyclo-Nexus fusion (this model)"]["pod"] > res_test["Physics detector, live rule (score ≥ 0.95)"]["pod"] \
        and res_test["Cyclo-Nexus fusion (this model)"]["fa_rate"] <= 0.08
    META.write_text(json.dumps({"features": cols, "threshold": float(thr), "auc_loso": float(auc), "approved": bool(passed),
                                "test": res_test["Cyclo-Nexus fusion (this model)"],
                                "trained": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}, indent=1), encoding="utf-8")

    def tab(res):
        out = ["| Detector | Systems found | False-alarm frames | Median centre error |", "|---|---|---|---|"]
        for k, s in res.items():
            out.append(f"| {k} | **{100 * s['pod']:.0f}%** ({s['found']}/{s['systems']}) | {100 * s['fa_rate']:.0f}% "
                       f"({s['fa_frames']}/{s['frames']}) | {s['median_err_km']:.0f} km |")
        return out

    lines = [
        "# Storm identification — detector fusion",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m forecaster.detection.fusion`.",
        "",
        f"**Data:** {df.frame.nunique()} INSAT-3DR/3DS frames (2018–2025) with IMERG rain, {len(df)} candidates from the "
        f"physics detector and YOLO-OBB; {int(df.label.sum())} lie within 300 km of a best-track system.",
        "**Validation:** leave-one-season-out — every season scored by a model that never saw it "
        f"(candidate ROC AUC {auc:.2f}). Threshold {thr:.2f}: most systems found with ≤ 5% false-alarm frames on 2018–23.",
        "",
        "## Every season 2018–2025", "", *tab(res_all), "",
        "## Test seasons 2024–25 (YOLO comparable only here)", "", *tab(res_test), "",
        "Most useful inputs: " + ", ".join(f"`{k}`" for k, _ in imp),
        "",
        f"**Used live: {'yes' if passed else 'no'}** (needs more systems found than the physics rule with ≤ 8% false-alarm frames on 2024–25).",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
