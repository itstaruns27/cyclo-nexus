"""
Satellite watch-area detector evaluation (master plan v4, Task 3.3)
═══════════════════════════════════════════════════════════════════
Runs the physics detector over every case built by build_case_set.py and reports, per
score threshold:
  * POD  — probability of detection: positives with a candidate within HIT_RADIUS_KM of the
           IBTrACS (official best-track) position;
  * FAR-day — fraction of negative days (no NI system within ±3 days) with any candidate;
  * mean position error of hits (candidate vs best track).
Writes docs/validation_report.md and data/validation/report.json.

Limits (stated in the report): the live SST/ocean filter is not applied here (Open-Meteo
marine returns current SST only), so live false-alarm rates should be lower than FAR-day.

Usage: python -m data_pipeline.validation.evaluate_detector
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from data_pipeline.preprocessing.physics_detector import PhysicsDetector, haversine_km  # noqa: E402

CASES = ROOT / "data" / "validation" / "cases.jsonl"
FRAMES = ROOT / "data" / "validation" / "frames"
REPORT_MD = ROOT / "docs" / "validation_report.md"
REPORT_JSON = ROOT / "data" / "validation" / "report.json"
HIT_RADIUS_KM = 500.0
THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9]


def main():
    cases = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    det = PhysicsDetector()
    rows = []
    for c in cases:
        window = np.stack([np.load(FRAMES / f)["tensor"] for f in c["frames"]])
        cands = [x for x in det.detect(window) if x.passes]
        best = None
        if c["kind"] == "positive":
            near = [(haversine_km(x.lat, x.lon, c["lat"], c["lon"]), x) for x in cands]
            near = [n for n in near if n[0] <= HIT_RADIUS_KM]
            best = max(near, key=lambda n: n[1].score) if near else None
        rows.append({
            "case_id": c["case_id"], "kind": c["kind"], "stage": c["stage"], "name": c["name"], "grade": c["grade"],
            "time": c["time"], "truth": [c["lat"], c["lon"]] if c["lat"] is not None else None,
            "hit_score": round(best[1].score, 3) if best else None,
            "hit_error_km": round(best[0]) if best else None,
            "max_score_anywhere": round(max((x.score for x in cands), default=0.0), 3),
            "candidates": [x.to_dict() for x in cands],
        })
        print(f"{c['case_id']:40s} {c['kind']:8s} hit={rows[-1]['hit_score']} err={rows[-1]['hit_error_km']} "
              f"max={rows[-1]['max_score_anywhere']}")

    pos = [r for r in rows if r["kind"] == "positive"]
    neg = [r for r in rows if r["kind"] == "negative"]
    table = []
    for t in THRESHOLDS:
        hits = [r for r in pos if r["hit_score"] is not None and r["hit_score"] >= t]
        fa = [r for r in neg if r["max_score_anywhere"] >= t]
        table.append({
            "threshold": t,
            "pod": round(len(hits) / len(pos), 3) if pos else None,
            "far_day": round(len(fa) / len(neg), 3) if neg else None,
            "mean_error_km": round(float(np.mean([r["hit_error_km"] for r in hits])), 0) if hits else None,
            "hits": len(hits), "positives": len(pos), "false_alarm_days": len(fa), "negatives": len(neg),
        })

    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "hit_radius_km": HIT_RADIUS_KM,
              "table": table, "cases": rows}
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Satellite Watch-Area Detector — Validation Report",
        "",
        f"Generated {report['generated_at'][:16]} UTC by `data_pipeline/validation/evaluate_detector.py`.",
        "",
        f"Real INSAT-3DS/3DR L1C + NASA IMERG windows (6 × 3-hourly) for {len(pos)} IBTrACS North Indian Ocean "
        f"cases (2024+) and {len(neg)} negative days (no NI system within ±3 days).",
        f"A hit = a passing candidate within {HIT_RADIUS_KM:.0f} km of the best-track position.",
        "",
        "| Score threshold | POD | False-alarm days | Mean hit error (km) |",
        "|---|---|---|---|",
    ]
    for r in table:
        lines.append(f"| {r['threshold']:.1f} | {r['hits']}/{r['positives']} ({r['pod']}) | "
                     f"{r['false_alarm_days']}/{r['negatives']} ({r['far_day']}) | {r['mean_error_km']} |")
    lines += [
        "",
        "## Cases",
        "",
        "| Case | Stage | System | Grade | Hit score | Error (km) | Max score anywhere |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['time'][:13]}Z | {r['kind']}/{r['stage']} | {r['name'] or '—'} | {r['grade'] or '—'} | "
                     f"{r['hit_score'] if r['hit_score'] is not None else '—'} | "
                     f"{r['hit_error_km'] if r['hit_error_km'] is not None else '—'} | {r['max_score_anywhere']} |")
    lines += [
        "",
        "## Limitations",
        "",
        "- Infrared-only organisation (DAV) locates the cloud-system centre, which can sit 100–400 km from the "
        "circulation centre of sheared systems; positions are shown with that uncertainty.",
        "- The live SST ≥ 26.5 °C / over-ocean filter (Open-Meteo marine) is not applied here because only "
        "current SST is available; live false-alarm rates should be lower than the FAR-day above.",
        "- The case set is small; numbers will change as more real cases are added.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(table, indent=2))
    print(f"Wrote {REPORT_MD} and {REPORT_JSON}")


if __name__ == "__main__":
    main()
