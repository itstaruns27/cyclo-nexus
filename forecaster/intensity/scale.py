"""IMD intensity classes (3-minute sustained wind, knots) — same thresholds as schemas/imd_scale.py."""

CLASSES = ["D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"]
LOWER_KT = [17, 28, 34, 48, 64, 90, 120]          # lower bound of each class; below 17 kt counts as D here


def imd_class(kt):
    """Index into CLASSES for a wind speed in knots."""
    i = 0
    for k, lo in enumerate(LOWER_KT):
        if kt >= lo:
            i = k
    return i
