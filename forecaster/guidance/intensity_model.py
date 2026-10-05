"""
Statistical-dynamical intensity forecast + rapid-intensification probability (master plan v5, Tasks 2.2, 2.4)
══════════════════════════════════════════════════════════════════════════════════════════════════════════════
  python -m forecaster.guidance.intensity_model

Like NHC's SHIPS/LGEM family: a gradient-boosted model per lead time predicts the intensity CHANGE from
  * every model's own predicted change (AIFS, ECMWF IFS + ensemble, GFS, HWRF, COAMPS-TC, UKMET, CMC …);
  * the storm now: real-time intensity (JTWC CARQ), its 12-hour trend, latitude, season, sea;
  * land along the consensus track (share of the next hours over land, hours until landfall) — North Indian
    Ocean storms weaken fast once they reach land, and global models often hold them too strong.
Rapid intensification (RI, ≥ 30 kt in 24 h, IMD/JTWC convention): probability from a classifier on the same inputs.

Fitted on seasons ≤ 2024, tested on 2025–26 (as the track consensus). Truth: JTWC best-track 1-minute wind.
Writes forecaster/weights/intensity_fc.json (+ one LightGBM text model per lead, ri_24.txt) and
docs/intensity_forecast_report.md.
"""

import json
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.guidance import consensus as C  # noqa: E402

WEIGHTS = ROOT / "forecaster" / "weights"
META = WEIGHTS / "intensity_fc.json"
REPORT = ROOT / "docs" / "intensity_forecast_report.md"
LEADS = [12, 24, 36, 48, 72]
INT_MODELS = ["AIFS", "GFS", "IFS", "IFS-ENSM", "AIFS-ENSM", "HWRF", "CTCX", "COTC", "UKM", "CMC", "AEMN"]
RI_KT = 30
PARAMS = dict(objective="regression", learning_rate=0.03, num_leaves=7, min_child_samples=15, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, seed=0)
ROUNDS = 350


@lru_cache(maxsize=1)
def land_grid():
    meta = json.loads((ROOT / "backend" / "data" / "pop_grid.json").read_text(encoding="utf-8"))
    grid = np.fromfile(ROOT / "backend" / "data" / "country_grid.bin", np.uint8).reshape(meta["rows"], meta["cols"])
    return grid, meta


def is_land(lat, lon):
    grid, m = land_grid()
    r = int((m["north"] - lat) / m["cell_deg"])
    c = int((((lon + 180) % 360) - 180 - m["west"]) / m["cell_deg"])
    if not (0 <= r < m["rows"] and 0 <= c < m["cols"]):
        return False
    return grid[r, c] > 0


def features(lead, v0, dv_past, lat, lon, month, cons_track, models):
    """One feature row. cons_track {tau: (lat, lon, …)}; models {name: {tau: (lat, lon, vmax)}}."""
    taus = [t for t in sorted(cons_track) if 0 < t <= lead]
    land = [is_land(*cons_track[t][:2]) for t in taus]
    first_land = next((t for t, l in zip(taus, land) if l), None)
    f = {"v0": v0, "dv_past12": dv_past, "abs_lat": abs(lat), "arabian_sea": float(lon < 77.5),
         "month_sin": np.sin(2 * np.pi * month / 12), "month_cos": np.cos(2 * np.pi * month / 12),
         "land_frac": float(np.mean(land)) if land else np.nan,
         "land_at_lead": float(land[-1]) if land and taus[-1] == lead else np.nan,
         "hours_to_land": float(first_land) if first_land is not None else 999.0,
         "on_land_now": float(is_land(lat, lon))}
    dvs = {}
    for m in INT_MODELS:
        tr = models.get(m)
        v = np.nan
        if tr and 0 in tr and lead in tr and tr[0][2] == tr[0][2] and tr[lead][2] == tr[lead][2]:
            v = tr[lead][2] - tr[0][2]
        f[f"dv_{m}"] = v
        dvs[m] = v
    ec = [dvs[m] for m in ("AIFS", "IFS", "IFS-ENSM") if dvs[m] == dvs[m]]
    al = [v for v in dvs.values() if v == v]
    f["dv_ecmwf_mean"] = float(np.mean(ec)) if ec else np.nan
    f["dv_all_mean"] = float(np.mean(al)) if al else np.nan
    f["rule"] = (C.intensity_at(models, lead, v0) - v0) if v0 == v0 else np.nan     # Phase-1 rule, as a predictor
    return f


def build_cases():
    g, storms, truth = C.load()
    det = C.ensemble_means(g)
    trk = C.tracks(det)
    pos = C.start_positions(trk, truth)
    settings = json.loads(C.WEIGHTS.read_text(encoding="utf-8"))
    rows = []
    for init, atcf, start in C.cases(trk, truth, pos):
        carq = trk.get(("CARQ", init, atcf), {}).get(0)
        v0 = carq[2] if carq and carq[2] == carq[2] else truth[(atcf, init)][2]
        prev = truth.get((atcf, init - pd.Timedelta(hours=12)))
        dv_past = truth[(atcf, init)][2] - prev[2] if prev and prev[2] == prev[2] else np.nan
        mem = C.member_forecasts(trk, init, atcf, start, settings["members"], settings["alphas"])
        cons = C.consensus(mem, settings["weights"], {}, start)
        models = {m: trk[(m, init, atcf)] for m in INT_MODELS if (m, init, atcf) in trk}
        for lead in LEADS:
            tv = truth.get((atcf, init + pd.Timedelta(hours=lead)))
            if tv is None or not (tv[2] >= C.MIN_TD_KT) or v0 != v0:
                continue
            f = features(lead, v0, dv_past, start[0], start[1], init.month, cons, models)
            rows.append({"atcf": atcf, "season": int(atcf[4:]), "init": init, "lead": lead, "v_true": tv[2],
                         "dv_true": tv[2] - v0, **f})
    return pd.DataFrame(rows)


def feature_cols(df):
    return [c for c in df.columns if c not in ("atcf", "season", "init", "lead", "v_true", "dv_true")]


def mae(a, b):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def main():
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score, brier_score_loss
    df = build_cases()
    cols = feature_cols(df)
    train_to, test_from = 2024, 2025
    out, models = [], {}
    lines_cv, lines_te = [], []
    for lead in LEADS:
        d = df[df.lead == lead]
        tr, te = d[d.season <= train_to], d[d.season >= test_from]
        # Leave-one-season-out on the training seasons (covers strong storms: Fani, Amphan, Mocha, Biparjoy …)
        oof = pd.Series(np.nan, index=tr.index)
        for s in sorted(tr.season.unique()):
            a, b = tr[tr.season != s], tr[tr.season == s]
            m = lgb.train(PARAMS, lgb.Dataset(a[cols], a.dv_true), ROUNDS)
            oof[b.index] = m.predict(b[cols])
        strong = tr.v0 >= 64
        lines_cv.append(f"| {lead} h | {len(tr)} | **{mae(tr.v0 + oof, tr.v_true):.1f}** | {mae(tr.v0 + tr.rule, tr.v_true):.1f} | "
                        f"{mae(tr.v0, tr.v_true):.1f} | **{mae((tr.v0 + oof)[strong], tr.v_true[strong]):.1f}** | "
                        f"{mae((tr.v0 + tr.rule)[strong], tr.v_true[strong]):.1f} |")
        final = lgb.train(PARAMS, lgb.Dataset(tr[cols], tr.dv_true), ROUNDS)
        final.save_model(str(WEIGHTS / f"intensity_fc_{lead}.txt"))
        models[lead] = final
        p = te.v0 + final.predict(te[cols])
        lines_te.append(f"| {lead} h | {len(te)} | **{mae(p, te.v_true):.1f}** | {mae(te.v0 + te.rule, te.v_true):.1f} | {mae(te.v0, te.v_true):.1f} |")
        out.append({"lead": lead, "test_mae": mae(p, te.v_true), "rule_mae": mae(te.v0 + te.rule, te.v_true),
                    "cv_mae": mae(tr.v0 + oof, tr.v_true), "cv_rule_mae": mae(tr.v0 + tr.rule, tr.v_true)})

    # Rapid intensification (24 h)
    d24 = df[df.lead == 24].copy()
    d24["ri"] = (d24.dv_true >= RI_KT).astype(int)
    tr = d24[d24.season <= train_to]
    rp = dict(PARAMS, objective="binary")
    oof = pd.Series(np.nan, index=tr.index)
    for s in sorted(tr.season.unique()):
        a, b = tr[tr.season != s], tr[tr.season == s]
        if a.ri.sum() < 3:
            continue
        m = lgb.train(rp, lgb.Dataset(a[cols], a.ri), 250)
        oof[b.index] = m.predict(b[cols])
    ok = oof.notna()
    auc = roc_auc_score(tr.ri[ok], oof[ok]) if tr.ri[ok].nunique() > 1 else float("nan")
    brier = brier_score_loss(tr.ri[ok], oof[ok])
    clim = brier_score_loss(tr.ri[ok], np.full(ok.sum(), tr.ri[ok].mean()))
    bins = pd.cut(oof[ok], [0, 0.1, 0.25, 0.5, 1.0], include_lowest=True)
    rel = tr[ok].groupby(bins, observed=True).ri.agg(["count", "mean"])
    rel["pred"] = oof[ok].groupby(bins, observed=True).mean()
    ri_model = lgb.train(rp, lgb.Dataset(tr[cols], tr.ri), 250)
    ri_model.save_model(str(WEIGHTS / "ri_24.txt"))
    te24 = d24[d24.season >= test_from]
    te_ri = int(te24.ri.sum())

    META.write_text(json.dumps({
        "trained": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "features": cols, "leads": LEADS,
        "train_seasons": f"<= {train_to}", "test_seasons": f">= {test_from}", "results": out,
        "ri": {"threshold_kt_24h": RI_KT, "cv_auc": auc, "cv_brier": brier, "cv_brier_climatology": clim,
               "base_rate": float(tr.ri.mean())},
        "use_model": all(r["test_mae"] <= r["rule_mae"] + 0.5 and r["cv_mae"] < r["cv_rule_mae"] for r in out),
    }, indent=1), encoding="utf-8")

    lines = [
        "# Intensity forecast and rapid-intensification probability — verification",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m forecaster.guidance.intensity_model`.",
        "Mean absolute error of the maximum sustained wind (kt, JTWC 1-minute). Start intensity = JTWC real-time (CARQ).",
        "Model = gradient-boosted change per lead (inputs: every model's predicted change, trend, latitude, season, land along the track).",
        "Rule = Phase-1 consensus intensity (current + AIFS/GFS change). Persistence = no change.",
        "",
        f"## Leave-one-season-out on 2018–{train_to} (each season predicted by a model that never saw it; includes the strong storms)",
        "",
        "| Lead | Cases | Model | Rule | Persistence | Model, storms ≥ 64 kt | Rule, ≥ 64 kt |",
        "|---|---|---|---|---|---|---|", *lines_cv,
        "",
        f"## Test seasons ≥ {test_from} (never used)",
        "",
        "| Lead | Cases | Model | Rule | Persistence |", "|---|---|---|---|---|", *lines_te,
        "",
        "IMD official intensity error, long-period average 2019–23: 7.1 / 10.3 / 13.8 kt at 24 / 48 / 72 h (3-minute wind; indicative).",
        "",
        f"## Rapid intensification (≥ {RI_KT} kt in 24 h)",
        "",
        f"Base rate {100 * tr.ri.mean():.1f}% of 24-h cases ({int(tr.ri.sum())} events, 2018–{train_to}). "
        f"Leave-one-season-out: ROC AUC **{auc:.2f}**, Brier {brier:.3f} vs {clim:.3f} for always forecasting the base rate "
        f"(skill {100 * (1 - brier / clim):.0f}%). Test seasons contain {te_ri} RI case(s) — too few to score separately.",
        "",
        "Reliability (leave-one-season-out):", "",
        "| Forecast probability | Cases | Mean forecast | Observed frequency |", "|---|---|---|---|",
        *[f"| {iv} | {int(r['count'])} | {100 * r['pred']:.0f}% | {100 * r['mean']:.0f}% |" for iv, r in rel.iterrows()],
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()


class IntensityForecaster:
    """Runtime use of the fitted models (forecaster/guidance/live.py). Falls back to None if not trained/approved."""

    def __init__(self):
        import lightgbm as lgb
        self.meta = json.loads(META.read_text(encoding="utf-8"))
        self.cols = self.meta["features"]
        self.models = {lead: lgb.Booster(model_file=str(WEIGHTS / f"intensity_fc_{lead}.txt")) for lead in self.meta["leads"]}
        self.ri = lgb.Booster(model_file=str(WEIGHTS / "ri_24.txt"))

    @classmethod
    def load(cls):
        try:
            f = cls()
            return f if f.meta.get("use_model") else None
        except Exception:  # noqa: BLE001
            return None

    def predict(self, v0, dv_past, lat, lon, month, cons_track, models):
        """({lead h: wind kt} for every 6-hourly lead up to the last model lead, P(RI in 24 h))."""
        pts = {0: v0}
        for lead, m in self.models.items():
            f = features(lead, v0, dv_past, lat, lon, month, cons_track, models)
            pts[lead] = max(15.0, v0 + float(m.predict(pd.DataFrame([f])[self.cols])[0]))
        f24 = features(24, v0, dv_past, lat, lon, month, cons_track, models)
        ri = float(self.ri.predict(pd.DataFrame([f24])[self.cols])[0])
        keys = sorted(pts)
        out = {h: float(np.interp(h, keys, [pts[k] for k in keys])) for h in range(6, keys[-1] + 1, 6)}
        return out, ri
