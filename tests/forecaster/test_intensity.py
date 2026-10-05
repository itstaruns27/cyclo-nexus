"""Satellite intensity features and IMD scale (forecaster/intensity) — offline tests on synthetic frames."""

import numpy as np

from forecaster.intensity.features import BBOX, DLAT, DLON, frame_features, refine_centre
from forecaster.intensity.scale import CLASSES, imd_class


def synthetic_storm(lat, lon, eye_km=15, ring_km=120, eye_k=290.0, ring_k=195.0, env_k=290.0):
    """(4, 512, 512) uint8 frame: warm eye inside a cold central dense overcast, clear surroundings."""
    rows = BBOX[1] - (np.arange(512) + 0.5) * DLAT
    cols = BBOX[2] + (np.arange(512) + 0.5) * DLON
    la, lo = np.meshgrid(rows, cols, indexing="ij")
    d = np.hypot((la - lat) * 111.2, (lo - lon) * 111.2 * np.cos(np.radians(lat)))
    tb = np.where(d < eye_km, eye_k, np.where(d < ring_km, ring_k, env_k))
    x = np.zeros((4, 512, 512), np.uint8)
    x[0] = np.clip((tb - 180) / 140, 1 / 255, 1) * 255
    x[1] = x[0]
    x[2] = 128
    x[3] = np.where(d < ring_km, 60, 0)
    return x


def test_imd_scale_boundaries():
    assert [CLASSES[imd_class(k)] for k in (20, 28, 34, 48, 64, 90, 120)] == CLASSES
    assert CLASSES[imd_class(33.9)] == "DD" and CLASSES[imd_class(63.9)] == "SCS"


def test_eye_auto_centring_finds_an_offset_eye():
    x = synthetic_storm(15.0, 88.0)
    lat, lon, score, found = refine_centre(x, 15.0 + 0.4, 88.0 - 0.3)     # given centre ≈ 55 km off
    assert found and score > 40
    assert abs(lat - 15.0) < 0.15 and abs(lon - 88.0) < 0.2


def test_features_see_the_eye_and_cold_cloud():
    f = frame_features(synthetic_storm(15.0, 88.0), 15.0, 88.0)
    assert f["eye_tb"] > 280 and f["eye_contrast"] > 80
    assert f["cold213_100"] > 0.9 and f["rain_mean_50"] > 20
    assert frame_features(synthetic_storm(15.0, 88.0), 40.0, 88.0) is None      # centre off the grid
