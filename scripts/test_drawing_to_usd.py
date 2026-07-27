#!/usr/bin/env python3
"""
test_drawing_to_usd.py — assert the extrusion stays watertight and correctly wound.

The winding bug this guards against is invisible in the output geometry and only
surfaces as an `nvidia_usd_validate` *warning* — which still exits 1. Cheap to
check directly, so check it directly.

    .venv-ov/bin/python scripts/test_drawing_to_usd.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawing_to_usd import extrude, prism_volume, signed_area, classify  # noqa: E402


def mesh_health(pts, counts, indices):
    """(watertight, consistently_wound) for a closed surface."""
    directed, undirected, k = Counter(), Counter(), 0
    for c in counts:
        f = indices[k:k + c]; k += c
        for i in range(c):
            a, b = int(f[i]), int(f[(i + 1) % c])
            directed[(a, b)] += 1
            undirected[(min(a, b), max(a, b))] += 1
    watertight = all(v == 2 for v in undirected.values())
    wound = all(v == 1 for v in directed.values())
    return watertight, wound


def ccw(pts):
    p = np.asarray(pts, float)
    return p if signed_area(p) > 0 else p[::-1]


def cw(pts):
    p = np.asarray(pts, float)
    return p if signed_area(p) < 0 else p[::-1]


def ring(cx, cy, r, n, clockwise=False):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if clockwise:
        t = -t
    return np.column_stack([cx + r * np.cos(t), cy + r * np.sin(t)])


FAILS = []


def check(name, outer, holes, *, expect_area=None, thickness=1.0):
    pts, counts, indices = extrude(outer, holes, thickness)
    wt, wound = mesh_health(pts, counts, indices)
    ok = wt and wound
    detail = ""
    if expect_area is not None:
        vol = prism_volume(np.asarray(outer, float),
                           [np.asarray(h, float) for h in holes], thickness)
        want = expect_area * thickness
        rel = abs(vol - want) / want
        detail = f" vol_err={rel:.2%}"
        if rel > 0.02:
            ok = False
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<34} "
          f"faces={len(counts):<5} watertight={wt} wound={wound}{detail}")
    if not ok:
        FAILS.append(name)


def main() -> int:
    print("extrusion invariants")
    sq = ccw([[0, 0], [10, 0], [10, 10], [0, 10]])
    hA = cw([[2, 2], [2, 4], [4, 4], [4, 2]])
    hB = cw([[6, 6], [6, 8], [8, 8], [8, 6]])

    check("plain square", sq, [], expect_area=100.0)
    check("one square hole", sq, [hA], expect_area=100.0 - 4.0)
    check("two disjoint holes", sq, [hA, hB], expect_area=100.0 - 8.0)
    check("circular hole", sq, [ring(5, 5, 1.5, 32, clockwise=True)],
          expect_area=100.0 - np.pi * 1.5 ** 2)
    check("many holes", sq, [cw(ring(x, y, 0.4, 12))
                             for x in (2, 5, 8) for y in (2, 5, 8)],
          expect_area=100.0 - 9 * np.pi * 0.4 ** 2)

    print("\ninput orientation is normalised, not trusted")
    check("CW boundary given", cw(sq), [], expect_area=100.0)
    check("CCW hole given", sq, [ccw(hA)], expect_area=100.0 - 4.0)
    check("CW boundary + CCW hole", cw(sq), [ccw(hA)], expect_area=100.0 - 4.0)

    print("\nshapes")
    check("thin sheet (0.5 mm)", sq, [hA], thickness=0.0005)
    check("disc with bore", ccw(ring(0, 0, 5, 64)),
          [cw(ring(0, 0, 2, 48))],
          expect_area=np.pi * (25 - 4))

    print("\nhole classification")
    loops = [np.asarray(sq, float), np.asarray(hA, float), np.asarray(hB, float)]
    outer, holes, outside = classify(loops)
    ok = (len(holes) == 2 and len(outside) == 0
          and abs(abs(signed_area(outer)) - 100.0) < 1e-6)
    print(f"  {'PASS' if ok else 'FAIL'}  largest loop becomes the boundary       "
          f"holes={len(holes)} outside={len(outside)}")
    if not ok:
        FAILS.append("classify")

    far = np.asarray(ccw([[20, 20], [22, 20], [22, 22], [20, 22]]), float)
    outer, holes, outside = classify(loops + [far])
    ok = len(holes) == 2 and len(outside) == 1
    print(f"  {'PASS' if ok else 'FAIL'}  a separate part is reported, not merged  "
          f"holes={len(holes)} outside={len(outside)}")
    if not ok:
        FAILS.append("classify-separate")

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} — {', '.join(FAILS)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
