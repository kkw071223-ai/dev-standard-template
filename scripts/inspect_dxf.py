#!/usr/bin/env python3
"""
inspect_dxf.py — look at a DXF before converting it.

Run this first on any real drawing. Production DXFs carry title blocks, centre
lines, hatches, construction geometry and often several parts, and
`drawing_to_usd.py` only extrudes *closed* profiles. This says what is in the
file, which layers hold usable geometry, and what command to run — instead of
letting the conversion fail with "no closed profiles found".

    .venv-ov/bin/python scripts/inspect_dxf.py mypart.dxf

Reads only; it never writes to the drawing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawing_to_usd import (  # noqa: E402
    DXF_UNITS, extract_loops, classify, signed_area, prism_volume,
)

# entities that describe a shape but cannot close one on their own
OPEN_KINDS = {"LINE", "ARC", "SPLINE", "ELLIPSE"}
# entities that are annotation, not geometry
NOISE_KINDS = {"DIMENSION", "TEXT", "MTEXT", "LEADER", "MULTILEADER", "HATCH",
               "ATTDEF", "ATTRIB", "POINT", "INSERT", "VIEWPORT", "SOLID", "WIPEOUT"}


def bbox_of(msp, layers=None):
    lo = np.array([np.inf, np.inf]); hi = np.array([-np.inf, -np.inf])
    for e in msp:
        if layers and e.dxf.layer not in layers:
            continue
        try:
            t = e.dxftype()
            if t == "LWPOLYLINE":
                p = np.array([(x, y) for x, y, *_ in e.get_points()])
            elif t == "POLYLINE":
                p = np.array([[v.dxf.location.x, v.dxf.location.y] for v in e.vertices])
            elif t == "CIRCLE":
                c, r = e.dxf.center, e.dxf.radius
                p = np.array([[c.x - r, c.y - r], [c.x + r, c.y + r]])
            elif t == "LINE":
                p = np.array([[e.dxf.start.x, e.dxf.start.y], [e.dxf.end.x, e.dxf.end.y]])
            elif t == "ARC":
                c, r = e.dxf.center, e.dxf.radius
                p = np.array([[c.x - r, c.y - r], [c.x + r, c.y + r]])
            else:
                continue
            if len(p):
                lo = np.minimum(lo, p.min(axis=0)); hi = np.maximum(hi, p.max(axis=0))
        except Exception:
            continue
    if not np.isfinite(lo).all():
        return None
    return lo, hi


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf")
    ap.add_argument("--units", default=None, help="override drawing units for the report")
    ap.add_argument("--json", default=None, help="also write the findings here")
    args = ap.parse_args()

    import ezdxf

    path = Path(args.dxf)
    if not path.exists():
        print(f"ERROR: no such file: {path}", file=sys.stderr)
        return 2

    try:
        doc = ezdxf.readfile(str(path))
    except ezdxf.DXFStructureError as exc:
        print(f"ERROR: not a readable DXF ({exc}).", file=sys.stderr)
        print("  If this is a DWG, convert it first: ODAFileConverter in.dwg out.dxf",
              file=sys.stderr)
        return 2

    msp = doc.modelspace()
    print(f"file      : {path}  ({path.stat().st_size/1024:.0f} KB)")
    print(f"dxf ver   : {doc.dxfversion}")

    # ── units
    code = doc.header.get("$INSUNITS", 0)
    factor, uname = DXF_UNITS.get(code, (None, "unknown"))
    if args.units:
        for f, n in DXF_UNITS.values():
            if n == args.units:
                factor, uname = f, args.units
    if factor is None:
        print("units     : NOT DECLARED ($INSUNITS=0) — drawing_to_usd will assume mm")
    else:
        print(f"units     : {uname}  (x{factor:g} to metres)")

    # ── entity mix
    per_layer = defaultdict(Counter)
    for e in msp:
        per_layer[e.dxf.layer][e.dxftype()] += 1
    total = Counter()
    for c in per_layer.values():
        total.update(c)
    print(f"entities  : {sum(total.values())} across {len(per_layer)} layer(s)")

    # ── is this one part, or a whole drawing set?
    # Worth answering before anything else: a production sheet set tiles several
    # framed sheets into one modelspace, and the largest frame then wins the
    # boundary contest. Everything downstream still "works" — it just extrudes
    # the title block.
    findings, suggestion, frame_layer = [], None, None
    n_insert = total.get("INSERT", 0)
    n_dim = total.get("DIMENSION", 0)
    scale_loops, _ = extract_loops(msp, None, 6.0)
    frames = []
    for lp in scale_loops:
        if len(lp) == 4:
            sz = lp.max(axis=0) - lp.min(axis=0)
            if min(sz) > 300:                      # A-series sheets, any unit
                frames.append((float(np.prod(sz)), float(sz[0]), float(sz[1])))
    frames.sort(reverse=True)

    assembly = len(frames) >= 2 or (n_insert > 50 and n_dim > 5)
    if assembly:
        findings.append("assembly-drawing-set")
        print()
        print("  VERDICT: this looks like an assembly / multi-sheet drawing SET,")
        print("           not a single part.")
        if len(frames) >= 2:
            print(f"           {len(frames)} sheet-frame rectangles: "
                  + ", ".join(f"{w:.0f}x{h:.0f}" for _, w, h in frames[:4]))
        if n_insert:
            print(f"           {n_insert} block references (INSERT), {n_dim} dimensions")
        print()
        print("           drawing_to_usd.py extrudes ONE closed profile. Given a set,")
        print("           it will extrude the largest rectangle — the title block.")
        print("           Render it to see what you have:")
        print(f"             python scripts/render_dxf.py {path} --out .out/look --split")
        print("           Then either isolate one flat part into its own DXF, or —")
        print("           if the subject is 3D equipment or piping — build the solid")
        print("           in CAD and bring it in via usd-convert-cad instead.")

    # ── closed loops per layer (the number that decides everything)
    print()
    print(f"  {'layer':<20} {'closed':>6} {'open':>5} {'noise':>6}  entity mix")
    print(f"  {'-'*20} {'-'*6} {'-'*5} {'-'*6}  {'-'*40}")
    usable, layer_rows = [], []
    for layer in sorted(per_layer):
        loops, _ = extract_loops(msp, {layer}, 6.0)
        kinds = per_layer[layer]
        n_open = sum(v for k, v in kinds.items() if k in OPEN_KINDS)
        n_noise = sum(v for k, v in kinds.items() if k in NOISE_KINDS)
        mix = " ".join(f"{k}x{v}" for k, v in sorted(kinds.items()))
        flag = " <-- geometry" if loops else ("  (chainable?)" if n_open else "")
        print(f"  {layer:<20} {len(loops):>6} {n_open:>5} {n_noise:>6}  {mix[:40]}{flag}")
        if loops:
            usable.append(layer)
        layer_rows.append({"layer": layer, "closed_loops": len(loops),
                           "open_entities": n_open, "annotation": n_noise,
                           "entities": dict(kinds)})

    # ── overall
    all_loops, skipped = extract_loops(msp, None, 6.0)
    print()
    print(f"closed profiles found : {len(all_loops)}")

    if not all_loops:
        print()
        print("PROBLEM: no closed profile — nothing can be extruded.")
        n_open_total = sum(v for k, v in total.items() if k in OPEN_KINDS)
        if n_open_total:
            print(f"  The drawing has {n_open_total} open segment(s) "
                  f"({', '.join(sorted(k for k in total if k in OPEN_KINDS))}).")
            print("  Profiles drawn as separate lines and arcs are common. Try:")
            print(f"    drawing_to_usd.py {path} out/ --thickness 0.01 --chain-tolerance 0.01")
            print("  or in your CAD tool, join the outline into a single closed polyline.")
            findings.append("no-closed-loops-but-open-segments")
        else:
            print("  No closed *or* open geometry was recognised. Check that the part")
            print("  is in modelspace rather than a block (INSERT) or paperspace.")
            findings.append("no-recognised-geometry")
    else:
        outer, holes, outside = classify(all_loops)
        bb = bbox_of(msp, set(usable) if usable else None)
        print(f"  boundary            : {len(outer)} points")
        print(f"  holes               : {len(holes)}")
        if outside:
            print(f"  loops outside it    : {len(outside)}  <-- separate parts, "
                  f"not holes; split the drawing")
            findings.append("multiple-parts")
        if bb is not None:
            lo, hi = bb
            size = hi - lo
            f = factor or 0.001
            print(f"  extents             : {size[0]:.3g} x {size[1]:.3g} {uname}"
                  f"   ({size[0]*f*1000:.1f} x {size[1]*f*1000:.1f} mm)")
            if factor is None:
                findings.append("units-not-declared")
            elif max(size * f) > 10:
                print("  NOTE: over 10 m across — units may be wrong")
                findings.append("suspiciously-large")
            elif max(size * f) < 0.001:
                print("  NOTE: under 1 mm across — units may be wrong")
                findings.append("suspiciously-small")

        area = abs(signed_area(outer)) - sum(abs(signed_area(h)) for h in holes)
        f = factor or 0.001
        area_m2 = area * f * f
        print(f"  profile area        : {area_m2*1e4:.2f} cm2")
        for t_mm in (3, 6, 12):
            v = prism_volume(outer, holes, t_mm / 1000.0 / f) * (f ** 3)
            print(f"      at {t_mm:>2} mm thick   -> {v*1e6:7.1f} cm3, "
                  f"{v*7850:6.3f} kg steel / {v*2700:.3f} kg aluminium")

        # Is the chosen boundary actually a title block? A drawing frame is a
        # plain rectangle spanning nearly the whole sheet, and because it is the
        # largest loop it wins the boundary contest — so the part gets extruded
        # as a hole in its own border. Worth catching, since the geometry is
        # valid and nothing downstream would complain.
        if bb is not None and len(outer) <= 8:
            lo, hi = bb
            sheet = float(np.prod(hi - lo))
            if sheet > 0 and abs(signed_area(outer)) / sheet > 0.9:
                # name the layer it came from, so it can be dropped by name
                for r in layer_rows:
                    if not r["closed_loops"]:
                        continue
                    ls, _ = extract_loops(msp, {r["layer"]}, 6.0)
                    if any(l.shape == outer.shape and np.allclose(l, outer) for l in ls):
                        frame_layer = r["layer"]
                        break
                print()
                print(f"  WARNING: the largest loop is a near-full-sheet rectangle"
                      + (f" on '{frame_layer}'" if frame_layer else "") + " —")
                print("           this looks like a drawing frame, not the part.")
                print("           It is excluded from the suggestion below.")
                findings.append("boundary-looks-like-frame")

    # Layers holding only open segments are where an exploded profile lives.
    chainable = [r["layer"] for r in layer_rows
                 if r["closed_loops"] == 0 and r["open_entities"] > 0]
    if chainable:
        print()
        print(f"  layers with open segments only: {', '.join(chainable)}")
        print("    A profile drawn as loose lines/arcs lands here. If your part is")
        print("    one of these, add --chain-tolerance (in drawing units) to join it.")

    unit_opt = "" if factor is not None else " --units mm"
    if all_loops or chainable:
        # Deliberately not auto-picking layers: which ones carry the part is a
        # judgement about *this* drawing, and a confident wrong guess costs more
        # than an explicit blank.
        cands = [l for l in usable + chainable if l != frame_layer]
        pick = ",".join(cands) if cands else "YOUR_LAYERS"
        chain_opt = " --chain-tolerance 0.01" if chainable else ""
        simple = (not chainable and not unit_opt and not frame_layer
                  and len(usable) == len(per_layer))
        suggestion = (f"./scripts/run_pipeline.sh {path}" if simple else
                      f".venv-ov/bin/python scripts/drawing_to_usd.py {path} .out/mypart"
                      f" --thickness 0.012 --layers {pick}{unit_opt}{chain_opt}")

    if skipped:
        print()
        print("ignored (not closed loops on their own):")
        for s in sorted(set(skipped))[:8]:
            print(f"  - {s}")

    print()
    if suggestion:
        print("suggested next step:")
        print(f"  {suggestion}")
        print("  set --thickness to the plate thickness IN METRES (0.012 = 12 mm),")
        print("  and check --layers lists only the layers holding the part itself.")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "file": str(path), "dxf_version": doc.dxfversion,
            "units": uname, "unit_scale_to_m": factor,
            "closed_profiles": len(all_loops),
            "layers": layer_rows, "usable_layers": usable,
            "chainable_layers": chainable, "frame_layer": frame_layer,
            "looks_like_assembly_set": assembly,
            "sheet_frames": [{"w": w, "h": h} for _, w, h in frames],
            "insert_count": n_insert, "dimension_count": n_dim,
            "findings": findings, "suggested_command": suggestion,
            "ignored": sorted(set(skipped)),
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
