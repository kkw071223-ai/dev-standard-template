#!/usr/bin/env python3
"""
drawing_set_to_usd.py — bring a whole 2D drawing into USD as 3D geometry.

`drawing_to_usd.py` extrudes ONE closed profile into a solid part. That is the
wrong shape of tool for an assembly or a multi-sheet set, where the drawing is
hundreds of views rather than one outline. This is the other conversion: take
everything the drawing contains and place it in a USD stage.

Two kinds of output, both real 3D geometry:

  curves   every line, arc, circle and polyline becomes a USD BasisCurves,
           grouped into one prim per layer, positioned in 3D space. This is the
           faithful conversion — nothing is invented and nothing is dropped.
  solids   closed profiles are additionally extruded into watertight meshes.
           Off unless you ask, because on an assembly drawing a closed loop is
           usually a silhouette of 3D equipment, and extruding it produces a
           slab that looks like a part but is not one.

Blocks (INSERT) are expanded recursively, so geometry stored inside block
definitions comes through with its placement applied.

    python drawing_set_to_usd.py plant.dxf out/plant --units mm
    python drawing_set_to_usd.py plant.dxf out/plant --units mm --solids --max-solid-mm 600
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
    DXF_UNITS, _arc_points, _bulge_points, resolve_scale,
    extrude, signed_area, classify, prism_volume,
)

MAX_INSERT_DEPTH = 6          # nested blocks; guards against a cyclic reference


def polylines_from(entity, seg_deg: float):
    """[(N,2) array, closed] for one entity, or [] if it carries no line work."""
    t = entity.dxftype()
    try:
        if t == "LINE":
            s, e = entity.dxf.start, entity.dxf.end
            return [(np.array([[s.x, s.y], [e.x, e.y]], float), False)]

        if t == "CIRCLE":
            c = entity.dxf.center
            return [(_arc_points(c.x, c.y, entity.dxf.radius, 0.0, 360.0, seg_deg)[:-1], True)]

        if t == "ARC":
            c = entity.dxf.center
            return [(_arc_points(c.x, c.y, entity.dxf.radius,
                                 entity.dxf.start_angle, entity.dxf.end_angle,
                                 seg_deg), False)]

        if t == "ELLIPSE":
            pts = [(p[0], p[1]) for p in entity.flattening(0.01)]
            return [(np.asarray(pts, float), bool(entity.closed))] if len(pts) > 1 else []

        if t == "SPLINE":
            pts = [(p[0], p[1]) for p in entity.flattening(0.01)]
            return [(np.asarray(pts, float), bool(entity.closed))] if len(pts) > 1 else []

        if t == "LWPOLYLINE":
            raw = list(entity.get_points("xyb"))
            out = []
            n = len(raw)
            for i, (x, y, b) in enumerate(raw):
                out.append([x, y])
                nxt = raw[(i + 1) % n]
                if abs(b) > 1e-12 and (i + 1 < n or entity.closed):
                    out.extend(_bulge_points((x, y), (nxt[0], nxt[1]), b, seg_deg)[1:])
            a = np.asarray(out, float)
            return [(a, bool(entity.closed))] if len(a) > 1 else []

        if t == "POLYLINE":
            a = np.array([[v.dxf.location.x, v.dxf.location.y] for v in entity.vertices], float)
            return [(a, bool(entity.is_closed))] if len(a) > 1 else []
    except Exception:
        return []
    return []


def walk(container, seg_deg: float, depth: int = 0):
    """Yield (layer, points, closed) for everything, expanding blocks in place."""
    for e in container:
        t = e.dxftype()
        if t == "INSERT":
            if depth >= MAX_INSERT_DEPTH:
                continue
            try:
                yield from walk(e.virtual_entities(), seg_deg, depth + 1)
            except Exception:
                continue
            continue
        layer = getattr(e.dxf, "layer", "0")
        for pts, closed in polylines_from(e, seg_deg):
            if len(pts) >= 2:
                yield layer, pts, closed


ACI = {  # AutoCAD colour index -> rgb, for the handful that actually get used
    1: (1.0, 0.15, 0.15), 2: (1.0, 1.0, 0.2), 3: (0.2, 1.0, 0.2),
    4: (0.2, 1.0, 1.0), 5: (0.25, 0.4, 1.0), 6: (1.0, 0.25, 1.0),
    7: (0.85, 0.85, 0.85), 8: (0.5, 0.5, 0.5), 9: (0.75, 0.75, 0.75),
}


def layer_color(doc, name):
    try:
        return ACI.get(doc.layers.get(name).color, (0.8, 0.8, 0.8))
    except Exception:
        return (0.8, 0.8, 0.8)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf")
    ap.add_argument("outdir")
    ap.add_argument("--name", default=None)
    ap.add_argument("--units", default=None, help="mm, cm, m, in, ft — overrides $INSUNITS")
    ap.add_argument("--layers", default=None, help="comma-separated subset")
    ap.add_argument("--arc-segment-deg", type=float, default=8.0)
    ap.add_argument("--solids", action="store_true",
                    help="also extrude closed profiles into meshes")
    ap.add_argument("--thickness", type=float, default=0.006,
                    help="extrusion depth in METRES for --solids (default 6 mm)")
    ap.add_argument("--min-solid-mm", type=float, default=15.0,
                    help="skip closed profiles smaller than this across")
    ap.add_argument("--max-solid-mm", type=float, default=1500.0,
                    help="skip closed profiles larger than this — excludes sheet frames")
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    import ezdxf
    from pxr import Usd, UsdGeom, Gf, Vt, Sdf

    src = Path(args.dxf).resolve()
    name = args.name or src.stem
    doc = ezdxf.readfile(str(src))
    msp = doc.modelspace()
    scale, unit_name = resolve_scale(doc, args.units)
    keep = set(s.strip() for s in args.layers.split(",")) if args.layers else None

    print(f"reading {src.name} ...")
    per_layer = defaultdict(list)
    closed_loops = []
    for layer, pts, closed in walk(msp, args.arc_segment_deg):
        if keep and layer not in keep:
            continue
        per_layer[layer].append(pts * scale)
        if closed and len(pts) >= 3:
            closed_loops.append((layer, pts * scale))
    total = sum(len(v) for v in per_layer.values())
    print(f"  {total} polylines across {len(per_layer)} layer(s), "
          f"{len(closed_loops)} closed")
    if not total:
        print("ERROR: no drawable geometry found", file=sys.stderr)
        return 2

    outdir = Path(args.outdir).resolve() / name
    outdir.mkdir(parents=True, exist_ok=True)
    usd_path = outdir / f"{name}.usd"

    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, f"/{name}")
    root.GetPrim().SetAssetInfoByKey("name", name)
    Usd.ModelAPI(root).SetKind("assembly")
    stage.SetDefaultPrim(root.GetPrim())
    curves_scope = UsdGeom.Scope.Define(stage, f"/{name}/Drawing")

    def safe(s):
        out = "".join(c if c.isalnum() else "_" for c in str(s))
        return ("L_" + out) if not out or out[0].isdigit() else out

    layer_stats = []
    for layer, polys in sorted(per_layer.items()):
        pts_flat, counts = [], []
        for p in polys:
            pts_flat.extend([Gf.Vec3f(float(x), float(y), 0.0) for x, y in p])
            counts.append(len(p))
        prim_path = f"/{name}/Drawing/{safe(layer)}"
        cv = UsdGeom.BasisCurves.Define(stage, prim_path)
        cv.CreateTypeAttr().Set(UsdGeom.Tokens.linear)
        cv.CreateWrapAttr().Set(UsdGeom.Tokens.nonperiodic)
        cv.CreateCurveVertexCountsAttr().Set(Vt.IntArray(counts))
        cv.CreatePointsAttr().Set(Vt.Vec3fArray(pts_flat))
        w = 0.0015
        cv.CreateWidthsAttr().Set(Vt.FloatArray([w] * len(pts_flat)))
        cv.SetWidthsInterpolation(UsdGeom.Tokens.vertex)
        cv.CreateDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*layer_color(doc, layer))]))
        ext = UsdGeom.Boundable.ComputeExtentFromPlugins(
            UsdGeom.Boundable(cv.GetPrim()), Usd.TimeCode.Default())
        if ext:
            cv.CreateExtentAttr().Set(ext)
        layer_stats.append({"layer": layer, "curves": len(counts),
                            "points": len(pts_flat), "prim": prim_path})
        print(f"    {layer:<12} {len(counts):>6} curves / {len(pts_flat):>7} points")

    # ── optional solids
    solids = []
    if args.solids:
        UsdGeom.Scope.Define(stage, f"/{name}/Solids")
        lo_m, hi_m = args.min_solid_mm / 1000.0, args.max_solid_mm / 1000.0
        made = 0
        for i, (layer, loop) in enumerate(closed_loops):
            sz = loop.max(axis=0) - loop.min(axis=0)
            across = float(max(sz))
            if across < lo_m or across > hi_m:
                continue
            try:
                pts3, counts3, idx3 = extrude(loop, [], args.thickness)
            except SystemExit:
                continue
            except Exception:
                continue
            made += 1
            p = f"/{name}/Solids/{safe(layer)}_{made:04d}"
            m = UsdGeom.Mesh.Define(stage, p)
            m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*v) for v in pts3]))
            m.CreateFaceVertexCountsAttr(Vt.IntArray(counts3.tolist()))
            m.CreateFaceVertexIndicesAttr(Vt.IntArray(idx3.tolist()))
            m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
            m.CreateExtentAttr(Vt.Vec3fArray(
                [Gf.Vec3f(*pts3.min(axis=0)), Gf.Vec3f(*pts3.max(axis=0))]))
            m.CreateDisplayColorAttr().Set(
                Vt.Vec3fArray([Gf.Vec3f(*layer_color(doc, layer))]))
            solids.append({"prim": p, "layer": layer,
                           "size_mm": [round(float(v) * 1000, 2) for v in sz],
                           "volume_m3": round(prism_volume(loop, [], args.thickness), 12)})
        print(f"  extruded {made} closed profile(s) "
              f"between {args.min_solid_mm:g} and {args.max_solid_mm:g} mm across")

    allpts = np.vstack([p for polys in per_layer.values() for p in polys])
    lo, hi = allpts.min(axis=0), allpts.max(axis=0)
    layer_root = stage.GetRootLayer()
    cld = dict(layer_root.customLayerData)
    cld["DrawingProvenance"] = {
        "source_drawing": str(src), "drawing_units": unit_name,
        "unit_scale_to_m": scale, "polylines": total,
        "layers": len(per_layer), "closed_loops": len(closed_loops),
        "solids_extruded": len(solids),
        "note": "Line work converted to USD curves in 3D space. Curves are the "
                "drawing itself, not a solid model of the subject.",
    }
    layer_root.customLayerData = cld
    layer_root.Save()

    report = {
        "input": str(src), "output_usd": str(usd_path),
        "units": unit_name, "unit_scale_to_m": scale,
        "polylines": total, "closed_loops": len(closed_loops),
        "extents_m": {"min": [round(float(v), 4) for v in lo],
                      "max": [round(float(v), 4) for v in hi],
                      "size": [round(float(v), 4) for v in (hi - lo)]},
        "layers": layer_stats, "solids": solids,
    }
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2))
    print(f"\nwrote {usd_path}  ({usd_path.stat().st_size/1024:.0f} KB)")
    print(f"  extents {(hi-lo)[0]:.2f} x {(hi-lo)[1]:.2f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
