"""
Verify NWP track guidance and fit the Cyclo-Nexus consensus forecast
════════════════════════════════════════════════════════════════════
  python -m forecaster.guidance.consensus --train-to 2024 --test-from 2025

Inputs  data/guidance/guidance.csv.gz + storms.json (forecaster/guidance/build.py)
Outputs forecaster/weights/consensus.json   members, per-lead weights, intensity model, cone radii
        docs/guidance_report.md             errors of every model and of the consensus (unseen seasons)

Method (what operational centres do, e.g. NHC TVCN / JTWC CONW):
  1. Each model track is shifted so its starting point is the real-time storm position (JTWC CARQ,
     or the IBTrACS provisional tcvitals position for the current season). The shift is applied
     in full at every lead — it removes the model's analysis error.
  2. Ensemble means (IFS-ENS, AIFS-ENS) count as members when ≥ 40% of the ensemble still has the storm.
  3. Consensus position = weighted mean of available members, weights ∝ 1 / (mean squared error)
     per lead time, fitted on the training seasons only; needs ≥ 2 members.
  4. Intensity = current intensity + mean change predicted by AIFS and GFS (else IFS / IFS-ENSM).
  5. Cone radius = 67th percentile of consensus error on the training seasons (NHC's definition).
Verification follows JTWC/NHC practice: the system is ≥ 25 kt (tropical depression) at the start
and at the verifying time; truth = JTWC best track (IBTrACS USA_*).
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.guidance.sources import great_circle_km  # noqa: E402

DATA = ROOT / "data" / "guidance"
WEIGHTS = ROOT / "forecaster" / "weights" / "consensus.json"
REPORT = ROOT / "docs" / "guidance_report.md"
LEADS = [0, 12, 24, 36, 48, 72, 96, 120]
# IMD (RSMC New Delhi) official track errors, km — Annual verification report 2024
# (https://rsmcnewdelhi.imd.gov.in/uploads/Annual_Veri_2024.pdf): long-period average 2019–23, and 2024.
IMD_OFFICIAL = {"LPA 2019–23": {24: 72, 48: 112, 72: 156}, "2024": {24: 56, 48: 110, 72: 174}}
ENS = {"IFS-ENS": "IFS-ENSM", "AIFS-ENS": "AIFS-ENSM"}
GFS = ("AVNX", "AVNO")                       # NCEP tracker on GFS (name changed over the years)
MIN_TD_KT = 25


# ─── loading ───────────────────────────────────────────────────────────────

def load():
    g = pd.read_csv(DATA / "guidance.csv.gz")
    g["init"] = pd.to_datetime(g["init"], utc=True)
    g = g[g["tau"] % 6 == 0]
    g.loc[g["model"].isin(GFS), "model"] = "GFS"
    storms = json.loads((DATA / "storms.json").read_text(encoding="utf-8"))
    truth = {}
    for atcf, s in storms.items():
        for t, la, lo, w in s["fixes"]:
            truth[(atcf, pd.Timestamp(t))] = (la, lo, w)
    return g, storms, truth


def ensemble_means(g):
    """Mean track of each ensemble while ≥ 40% of its members still carry the storm; plus member spread."""
    out = []
    for model, name in ENS.items():
        e = g[g["model"] == model]
        if e.empty:
            continue
        n0 = e[e["tau"] == 0].groupby(["init", "atcf"])["member"].nunique().rename("n0")
        m = e.groupby(["init", "atcf", "tau"]).agg(lat=("lat", "mean"), lon=("lon", "mean"), vmax_kt=("vmax_kt", "mean"),
                                                   pmin_hpa=("pmin_hpa", "mean"), n=("member", "nunique")).reset_index()
        m = m.join(n0, on=["init", "atcf"])
        m = m[m["n"] >= np.maximum(5, 0.4 * m["n0"].fillna(m["n"]))]
        m["model"], m["member"] = name, 0
        out.append(m[["model", "init", "atcf", "member", "tau", "lat", "lon", "vmax_kt", "pmin_hpa"]])
    return pd.concat([g[g["member"] == 0]] + out, ignore_index=True)


def tracks(det):
    """{(model, init, atcf): {tau: (lat, lon, vmax)}}"""
    out = defaultdict(dict)
    for r in det.itertuples(index=False):
        out[(r.model, r.init, r.atcf)][int(r.tau)] = (r.lat, r.lon, r.vmax_kt)
    return out


def start_positions(trk, truth):
    """Real-time position at each (init, atcf): CARQ τ0 where JTWC published one, else IBTrACS (tcvitals for the live season)."""
    pos = {}
    for (model, init, atcf), tr in trk.items():
        if model == "CARQ" and 0 in tr:
            pos[(init, atcf)] = tr[0][:2] + (truth.get((atcf, init), (None, None, np.nan))[2],)
    for (atcf, t), v in truth.items():
        pos.setdefault((t, atcf), v)
    return pos


# ─── forecasts ─────────────────────────────────────────────────────────────

def shifted(tr, start, alpha=1.0):
    """Model track moved by `alpha` × (real-time position − model τ0); None if the model has no τ0.
    alpha is fitted per model: ECMWF's own analysis is often closer to the final best track than the
    real-time estimate, so moving it all the way can hurt."""
    if 0 not in tr:
        return None
    dlat, dlon = alpha * (start[0] - tr[0][0]), alpha * (start[1] - tr[0][1])
    return {tau: (la + dlat, lo + dlon, v) for tau, (la, lo, v) in tr.items()}


def persistence(atcf, init, truth, start):
    """Straight-line extrapolation of the last 12 h of motion (the classic no-skill baseline)."""
    prev = truth.get((atcf, init - pd.Timedelta(hours=12)))
    if prev is None:
        return None
    vlat, vlon = (start[0] - prev[0]) / 12, (start[1] - prev[1]) / 12
    return {tau: (start[0] + vlat * tau, start[1] + vlon * tau, start[2]) for tau in LEADS}


def blend(members, weights, lead):
    """Weighted mean position of the members that reach `lead`."""
    pts = [(weights.get(m, {}).get(str(lead), 0.0), tr[lead]) for m, tr in members.items() if lead in tr]
    pts = [(w, p) for w, p in pts if w > 0]
    if len(pts) < 2:
        return None
    w = np.array([a for a, _ in pts])
    la = np.array([p[0] for _, p in pts]); lo = np.array([p[1] for _, p in pts])
    v = np.array([p[2] for _, p in pts], float)
    vm = np.nanmean(v) if np.isfinite(v).any() else np.nan
    return float((w * la).sum() / w.sum()), float((w * lo).sum() / w.sum()), vm, len(pts)


def cases(trk, truth, pos):
    """Verification cases: (init, atcf) where the system is ≥ TD at the start, with the start position."""
    keys = {(init, atcf) for (_, init, atcf) in trk}
    out = []
    for init, atcf in sorted(keys):
        tv = truth.get((atcf, init))
        if tv is None or not (tv[2] >= MIN_TD_KT) or int(atcf[2:4]) >= 70:
            continue
        out.append((init, atcf, pos.get((init, atcf), tv)))
    return out


def errors(fc, atcf, init, truth):
    """{lead: (track km, intensity error kt)} where the verifying system is still ≥ TD."""
    out = {}
    for lead in LEADS:
        p = fc.get(lead)
        tv = truth.get((atcf, init + pd.Timedelta(hours=lead)))
        if p is None or tv is None or not (tv[2] >= MIN_TD_KT):
            continue
        out[lead] = (float(great_circle_km(p[0], p[1], tv[0], tv[1])), (p[2] - tv[2]) if p[2] == p[2] else np.nan)
    return out


# ─── fitting ───────────────────────────────────────────────────────────────

def member_forecasts(trk, init, atcf, start, models, alphas=None):
    out = {}
    for m in models:
        tr = trk.get((m, init, atcf))
        if tr:
            s = shifted(tr, start, (alphas or {}).get(m, 1.0))
            if s:
                out[m] = s
    return out


ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
ANCHOR = "GFS"          # reference model present in every season: weights are fitted on cases shared with it


def fit_alphas(trk, truth, train, models):
    """Per model, the shift fraction with the lowest mean 12–48 h error on the training cases."""
    out = {}
    for m in models:
        best = (1e18, 1.0)
        for a in ALPHAS:
            errs = []
            for init, atcf, start in train:
                tr = trk.get((m, init, atcf))
                s = shifted(tr, start, a) if tr else None
                if s:
                    errs += [km for lead, (km, _) in errors(s, atcf, init, truth).items() if 12 <= lead <= 48]
            if len(errs) >= 30 and np.mean(errs) < best[0]:
                best = (float(np.mean(errs)), a)
        out[m] = best[1]
    return out


def fit(trk, truth, pos, train, models, alphas):
    """Per-lead weights and intensity regression on the training cases.

    Weight of a model at a lead = 1 / (its MSE relative to the anchor's MSE on the cases both share),
    so a model is not rewarded for only running in easy seasons."""
    se = defaultdict(list)          # (model, lead) → [(model km², anchor km²)]
    dv_rows = defaultdict(list)
    for init, atcf, start in train:
        mem = member_forecasts(trk, init, atcf, start, models, alphas)
        ref = errors(mem[ANCHOR], atcf, init, truth) if ANCHOR in mem else {}
        for m, fc in mem.items():
            for lead, (km, _) in errors(fc, atcf, init, truth).items():
                if lead in ref:
                    se[(m, lead)].append((km ** 2, ref[lead][0] ** 2))
        for lead in LEADS[1:]:
            tv = truth.get((atcf, init + pd.Timedelta(hours=lead)))
            if tv is None or not (tv[2] >= MIN_TD_KT) or not (start[2] == start[2]):
                continue
            dv = [fc[lead][2] - fc[0][2] for fc in mem.values() if lead in fc and 0 in fc and fc[lead][2] == fc[lead][2] and fc[0][2] == fc[0][2]]
            if dv:
                dv_rows[lead].append((start[2], float(np.mean(dv)), tv[2]))
    weights = {m: {} for m in models}
    for lead in LEADS[1:]:
        for m in models:
            pairs = np.array(se[(m, lead)])
            if len(pairs) >= 15:
                ratio = (pairs[:, 0].mean() + 25 ** 2) / (pairs[:, 1].mean() + 25 ** 2)   # +25² km² regularises
                weights[m][str(lead)] = round(1.0 / ratio, 4)
    intensity = {}
    for lead, rows in dv_rows.items():
        a = np.array(rows)
        if len(a) < 20:
            continue
        X = np.c_[np.ones(len(a)), a[:, 0], a[:, 1]]
        coef, *_ = np.linalg.lstsq(X, a[:, 2], rcond=None)
        intensity[str(lead)] = [round(float(c), 4) for c in coef]       # v(lead) = c0 + c1·v0 + c2·Δv_models
    return weights, intensity


# Selected consensus: the members that were best together on the training seasons (equal weights).
# Chosen on 2023–24 among fixed sets (AIFS; AIFS+IFS-ENSM; +IFS; +AIFS-ENSM; +UKM; +GFS; all), then
# confirmed on 2025–26. When fewer than two of them are available the fitted all-model blend is used.
PRIMARY = ("AIFS", "IFS-ENSM")


INTENSITY_MEMBERS = (("AIFS", "GFS"), ("IFS", "IFS-ENSM"))


def intensity_at(mem, lead, v0):
    """Current intensity + the mean change the best intensity models predict (AIFS, GFS; else IFS, IFS-ENSM).
    A fitted scale factor came out ≈ 1 at every lead on 2018–24, so the change is used as is."""
    if v0 != v0:
        return np.nan
    for group in INTENSITY_MEMBERS:
        dv = [mem[m][lead][2] - mem[m][0][2] for m in group
              if m in mem and lead in mem[m] and 0 in mem[m] and mem[m][lead][2] == mem[m][lead][2] and mem[m][0][2] == mem[m][0][2]]
        if dv:
            return max(15.0, v0 + float(np.mean(dv)))
    return v0


def consensus(mem, weights, intensity, start, primary=PRIMARY):
    fc = {0: (start[0], start[1], start[2])}
    for lead in LEADS[1:]:
        prim = {m: mem[m] for m in primary if m in mem and lead in mem[m]}
        b = blend(prim, {m: {str(lead): 1.0} for m in prim}, lead) if len(prim) >= 2 else blend(mem, weights, lead)
        if b is None:
            continue
        la, lo, _, n = b
        fc[lead] = (la, lo, intensity_at(mem, lead, start[2]))
    return fc


# ─── report ────────────────────────────────────────────────────────────────

def table(err, names, leads, what=0, homogeneous=None):
    """Markdown table of mean errors (count) per model and lead; optional homogeneous sample over `homogeneous`."""
    lines = ["| Model | " + " | ".join(f"{l} h" for l in leads) + " |", "|---|" + "---|" * len(leads)]
    for m in names:
        cells = []
        for lead in leads:
            keys = set(err[m].get(lead, {}))
            if homogeneous:
                for o in homogeneous:
                    keys &= set(err[o].get(lead, {}))
            vals = [abs(err[m][lead][k][what]) for k in keys if err[m][lead][k][what] == err[m][lead][k][what]]
            cells.append(f"{np.mean(vals):.0f} ({len(vals)})" if vals else "—")
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-to", type=int, default=2024)
    ap.add_argument("--test-from", type=int, default=2025)
    args = ap.parse_args()

    g, storms, truth = load()
    det = ensemble_means(g)
    trk = tracks(det)
    pos = start_positions(trk, truth)
    every = cases(trk, truth, pos)
    season = lambda atcf: int(atcf[4:])  # noqa: E731
    train = [c for c in every if season(c[1]) <= args.train_to]
    test = [c for c in every if season(c[1]) >= args.test_from]

    # Candidate members: global models with a live open feed (ECMWF open data, RAL real-time a-decks)
    counts = det[det["tau"] == 48].groupby("model").size()
    models = [m for m in ["IFS", "AIFS", "IFS-ENSM", "AIFS-ENSM", "GFS", "AEMN", "UKM", "CMC", "CEMN", "NGX", "NVGM", "NEMN"]
              if counts.get(m, 0) >= 20]
    alphas = fit_alphas(trk, truth, train, models)
    weights, intensity = fit(trk, truth, pos, train, models, alphas)

    # Errors on every case for every model, raw + shifted, persistence and consensus
    err = defaultdict(lambda: defaultdict(dict))
    cons_err_train = defaultdict(list)
    for init, atcf, start in every:
        key = (init, atcf)
        split = "train" if season(atcf) <= args.train_to else "test" if season(atcf) >= args.test_from else None
        p = persistence(atcf, init, truth, start)
        if p:
            for lead, e in errors(p, atcf, init, truth).items():
                err[f"Persistence|{split}"][lead][key] = e
        mem = member_forecasts(trk, init, atcf, start, models, alphas)
        for m in models:
            tr = trk.get((m, init, atcf))
            if tr:
                for lead, e in errors(tr, atcf, init, truth).items():
                    err[f"{m} (raw)|{split}"][lead][key] = e
            if m in mem:
                for lead, e in errors(mem[m], atcf, init, truth).items():
                    err[f"{m}|{split}"][lead][key] = e
        eq = consensus(mem, {m: {str(l): 1.0 for l in LEADS} for m in mem}, intensity, start, primary=())
        for lead, e in errors(eq, atcf, init, truth).items():
            if lead:
                err[f"Equal-weight consensus|{split}"][lead][key] = e
        cw = consensus(mem, weights, intensity, start)
        for lead, e in errors(cw, atcf, init, truth).items():
            if lead:
                err[f"Cyclo-Nexus consensus|{split}"][lead][key] = e
                if split == "train" and season(atcf) >= 2023:      # ECMWF era = what the live forecast uses
                    cons_err_train[lead].append(e[0])

    cone = {str(l): round(float(np.percentile(v, 67)), 1) for l, v in cons_err_train.items() if len(v) >= 10}
    split_err = lambda split: {k.split("|")[0]: v for k, v in err.items() if k.endswith(f"|{split}")}  # noqa: E731
    te, tr_ = split_err("test"), split_err("train")
    leads = [12, 24, 36, 48, 72, 96, 120]

    def ranked(e):
        return sorted(e, key=lambda m: np.mean([v[0] for v in e[m].get(48, {}).values()]) if e[m].get(48) else 1e9)

    test_storms = sorted({c[1] for c in test})
    names = lambda a: ", ".join(f"{storms[x]['name'].title()} ({x})" for x in a if x in storms)  # noqa: E731
    homo = ["Cyclo-Nexus consensus", "Persistence"] + [m for m in ("IFS", "GFS", "AIFS") if m in te]
    best = {l: min(((m, np.mean([v[0] for v in te[m][l].values()])) for m in te if te[m].get(l) and "(raw)" not in m
                    and len(te[m][l]) >= 0.5 * len(te["Cyclo-Nexus consensus"].get(l, {}))), key=lambda x: x[1], default=(None, None))
            for l in leads}

    report = [
        "# Track guidance and consensus — verification",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m forecaster.guidance.consensus`.",
        "",
        f"**Truth:** JTWC best track (IBTrACS v04 USA_*), cases where the system is ≥ {MIN_TD_KT} kt at the start and at the verifying time.",
        f"**Fitted on:** seasons ≤ {args.train_to} ({len(train)} forecast cases). **Tested on:** seasons ≥ {args.test_from} "
        f"({len(test)} cases, never used for fitting): {names(test_storms)}.",
        "",
        "Errors are great-circle distances (km) between forecast and best-track centre; numbers in brackets are case counts.",
        "Models: IFS = ECMWF HRES; AIFS = ECMWF's AI model; -ENSM = ensemble mean; GFS = NCEP; UKM, CMC, NGX = UK, Canada, US Navy.",
        "\"(raw)\" = the model's own track; otherwise the track is moved towards the real-time storm position by a fraction fitted per model (listed below).",
        "",
        f"## Test seasons (≥ {args.test_from}) — all available cases",
        "",
        table(te, ranked(te), leads),
        "",
        f"## Test seasons — homogeneous sample ({', '.join(homo)})",
        "",
        table(te, homo + ["Equal-weight consensus"], leads, homogeneous=homo),
        "",
        "## Intensity error (kt), test seasons",
        "",
        table(te, ["Cyclo-Nexus consensus", "Persistence"] + [m for m in ("IFS", "GFS", "AIFS", "IFS-ENSM") if m in te], [12, 24, 48, 72], what=1,
              homogeneous=["Cyclo-Nexus consensus", "Persistence"]),
        "",
        f"## Training seasons (≤ {args.train_to}) — for reference",
        "",
        table(tr_, ranked(tr_), leads),
        "",
        "## Consensus settings (forecaster/weights/consensus.json)",
        "",
        f"Primary members (equal weights, used whenever both are available): {', '.join(PRIMARY)}. "
        "Otherwise all available members are blended with the fitted weights below.",
        "",
        "Relative weight per lead (higher = trusted more):",
        "",
        "| Member | " + " | ".join(f"{l} h" for l in leads) + " |",
        "|---|" + "---|" * len(leads),
    ]
    for m in models:
        tot = {l: sum(weights[x].get(str(l), 0) for x in models) or 1 for l in leads}
        report.append(f"| {m} | " + " | ".join(f"{weights[m].get(str(l), 0) / tot[l]:.2f}" for l in leads) + " |")
    report += ["", "Shift towards the real-time position (fraction of the start-point difference): "
               + ", ".join(f"{m} {alphas[m]:.2f}" for m in models), ""]
    hit = {l: np.mean([v[0] <= cone[str(l)] for v in te["Cyclo-Nexus consensus"][l].values()])
           for l in leads if str(l) in cone and te.get("Cyclo-Nexus consensus", {}).get(l)}
    report += ["", "Cone radius (67% of 2023–24 consensus errors; NHC's definition): "
               + ", ".join(f"{l} h {cone[str(l)]:.0f} km" for l in leads if str(l) in cone) + ".",
               "Share of unseen-season positions inside the cone (target ≈ 67%): "
               + ", ".join(f"{l} h {100 * h:.0f}%" for l, h in hit.items()) + ".", ""]
    cons = {l: float(np.mean([v[0] for v in te["Cyclo-Nexus consensus"][l].values()])) for l in (24, 48, 72)
            if te.get("Cyclo-Nexus consensus", {}).get(l)}
    lpa = IMD_OFFICIAL["LPA 2019–23"]
    passed = all(cons.get(l, 1e9) <= lpa[l] for l in (48, 72))
    report += ["## Comparison with the official forecast (IMD)", "",
               "| | 24 h | 48 h | 72 h |", "|---|---|---|---|",
               "| **Cyclo-Nexus consensus, unseen seasons** | " + " | ".join(f"**{cons[l]:.0f}**" if l in cons else "—" for l in (24, 48, 72)) + " |"]
    report += [f"| IMD official, {k} | " + " | ".join(str(v[l]) for l in (24, 48, 72)) + " |" for k, v in IMD_OFFICIAL.items()]
    report += ["", "IMD verifies against its own best track and includes depressions; the consensus is verified against JTWC's "
               "best track — so the comparison is indicative, not like-for-like.", "",
               f"**Task 1.3 acceptance (≤ official error at 48–72 h): {'PASS' if passed else 'NOT MET'}.** "
               + ("The AI consensus forecast may be shown on the site (AI_FORECAST_ENABLED)." if passed else
                  "Keep AI_FORECAST_ENABLED off."), ""]
    report += ["## Best on unseen seasons, per lead", ""] + [f"- {l} h: **{best[l][0]}** {best[l][1]:.0f} km" for l in leads if best[l][0]]
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS.write_text(json.dumps({
        "version": 1, "trained": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "train_seasons": f"<= {args.train_to}", "test_seasons": f">= {args.test_from}",
        "passed_official_check": bool(passed), "members": models, "primary": list(PRIMARY), "alphas": alphas, "weights": weights, "intensity": intensity, "cone_km": cone,
        "test_mean_km": {str(l): round(float(np.mean([v[0] for v in te["Cyclo-Nexus consensus"][l].values()])), 1)
                         for l in leads if te.get("Cyclo-Nexus consensus", {}).get(l)},
    }, indent=1), encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
