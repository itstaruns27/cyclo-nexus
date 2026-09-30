# YOLO-OBB Label Format Specification

Each annotation line: `class_id x_c y_c w h θ`

- `class_id`: Integer (0–6) mapping to IMD categories: D=0, DD=1, CS=2, SCS=3, VSCS=4, ESCS=5, SuCS=6
- `x_c, y_c`: Normalized center coordinates [0.0, 1.0]
- `w, h`: Normalized width/height of rotated box [0.0, 1.0]
- `θ`: Rotation angle in radians, range [-π/2, π/2]

## Example

```
6 0.512 0.489 0.185 0.156 0.35
```
This represents a Super Cyclonic Storm (class 6) with center at (51.2%, 48.9%), rotated box of 18.5% × 15.6% image dimensions, rotated 0.35 radians.
