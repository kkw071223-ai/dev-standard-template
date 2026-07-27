#!/usr/bin/env python3
"""
make_messy_dxf.py — a drawing with the problems real drawings have.

The bracket fixture is clean by construction, which proves nothing about a file
exported from someone else's CAD seat. This one deliberately carries the four
failure modes that actually show up, so `inspect_dxf.py` and the chaining path
have something real to catch:

  1. no declared units ($INSUNITS = 0)
  2. the outline drawn as loose LINE and ARC entities, not a closed polyline
  3. a title block and centre lines on their own layers
  4. a second, unrelated part in the same file

    python make_messy_dxf.py examples/drawing/messy.dxf
"""

from __future__ import annotations

import sys

import ezdxf


def main(path: str) -> int:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 0            # problem 1: units not declared
    msp = doc.modelspace()

    for lyr, color in (("OUTLINE", 7), ("HOLES", 1), ("CENTER", 4),
                       ("BORDER", 8), ("PART2", 2)):
        if lyr not in doc.layers:
            doc.layers.add(lyr, color=color)

    # problem 2: a 120 x 60 plate with two rounded ends, drawn as separate
    # LINE and ARC entities the way an exploded or imported profile arrives
    L, H, R = 120.0, 60.0, 30.0
    x0, x1 = -L / 2 + R, L / 2 - R
    msp.add_line((x0, -H / 2), (x1, -H / 2), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((x1, H / 2), (x0, H / 2), dxfattribs={"layer": "OUTLINE"})
    msp.add_arc(center=(x1, 0), radius=R, start_angle=-90, end_angle=90,
                dxfattribs={"layer": "OUTLINE"})
    msp.add_arc(center=(x0, 0), radius=R, start_angle=90, end_angle=270,
                dxfattribs={"layer": "OUTLINE"})

    # a proper closed hole, so the file is not uniformly broken
    msp.add_circle((0, 0), 12.0, dxfattribs={"layer": "HOLES"})

    # problem 3: annotation and construction geometry
    msp.add_line((-L, 0), (L, 0), dxfattribs={"layer": "CENTER"})
    msp.add_line((0, -H), (0, H), dxfattribs={"layer": "CENTER"})
    msp.add_lwpolyline([(-200, -120), (200, -120), (200, 120), (-200, 120)],
                       close=True, dxfattribs={"layer": "BORDER"})
    msp.add_text("PART A — 6mm, UNITS NOT SET", height=7,
                 dxfattribs={"layer": "BORDER"}).set_placement((-195, 105))

    # problem 4: an unrelated second part in the same drawing
    msp.add_lwpolyline([(150, -40), (190, -40), (190, 40), (150, 40)],
                       close=True, dxfattribs={"layer": "PART2"})

    doc.saveas(path)
    print(f"wrote {path}")
    print("  deliberately includes:")
    print("    - no $INSUNITS")
    print("    - outline as 2 LINE + 2 ARC (not a closed polyline)")
    print("    - CENTER / BORDER layers to be excluded")
    print("    - a second part (PART2) outside the main boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "messy.dxf"))
