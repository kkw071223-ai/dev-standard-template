#!/usr/bin/env python3
"""
make_bracket_dxf.py — generate the test drawing used by the DXF pipeline.

A mounting bracket the way a real drawing would carry it: millimetres, an outer
profile with filleted corners (as polyline bulges), four bolt holes and a
lightening slot. Deliberately includes a dimension line and a text note on
separate layers, so the converter has non-geometry entities to ignore.

    python make_bracket_dxf.py examples/drawing/bracket.dxf
"""

from __future__ import annotations

import math
import sys

import ezdxf


def rounded_rect(w, h, r):
    """Corner-filleted rectangle as (x, y, bulge) vertices centred on origin.

    A 90-degree arc has bulge = tan(90/4) = 0.4142.
    """
    b = math.tan(math.radians(90) / 4)
    x, y = w / 2 - r, h / 2 - r
    return [
        (-x, -h / 2, 0), (x, -h / 2, b),
        (w / 2, -y, 0), (w / 2, y, b),
        (x, h / 2, 0), (-x, h / 2, b),
        (-w / 2, y, 0), (-w / 2, -y, b),
    ]


def main(path: str) -> int:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4          # millimetres — the usual for mechanical work
    msp = doc.modelspace()

    for lyr, color in (("PROFILE", 7), ("HOLES", 1), ("DIMS", 3), ("NOTES", 5)):
        if lyr not in doc.layers:
            doc.layers.add(lyr, color=color)

    W, H, R = 180.0, 90.0, 12.0
    msp.add_lwpolyline(rounded_rect(W, H, R), format="xyb",
                       close=True, dxfattribs={"layer": "PROFILE"})

    # M8 clearance holes, 20 mm in from each corner
    for sx in (-1, 1):
        for sy in (-1, 1):
            msp.add_circle((sx * (W / 2 - 20), sy * (H / 2 - 20)), 4.5,
                           dxfattribs={"layer": "HOLES"})

    # central lightening slot — a stadium shape, two 180-degree bulges
    sl, sr = 70.0, 14.0
    msp.add_lwpolyline(
        [(-sl / 2, -sr, 0), (sl / 2, -sr, 1.0), (sl / 2, sr, 0), (-sl / 2, sr, 1.0)],
        format="xyb", close=True, dxfattribs={"layer": "HOLES"})

    # non-geometry the converter must ignore
    msp.add_linear_dim(base=(0, -H / 2 - 22), p1=(-W / 2, -H / 2),
                       p2=(W / 2, -H / 2), dxfattribs={"layer": "DIMS"}).render()
    msp.add_text("BRACKET, MTG — 12mm PLATE, STEEL",
                 height=6, dxfattribs={"layer": "NOTES"}).set_placement((-W / 2, H / 2 + 14))

    doc.saveas(path)
    print(f"wrote {path}")
    print(f"  units       : mm ($INSUNITS=4)")
    print(f"  profile     : {W:.0f} x {H:.0f} mm, R{R:.0f} fillets")
    print(f"  holes       : 4 x O9 mm + {sl:.0f}x{2*sr:.0f} mm slot")
    print(f"  also present: 1 dimension, 1 text note (must be ignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "bracket.dxf"))
