#!/usr/bin/env python3
"""
drawing_to_usd.py — turn a 2D engineering drawing (DXF) into a simulatable USD solid.

There is no NVIDIA skill for this step. `usd-convert-cad` handles 3D CAD
(STEP/JT/DGN/HOOPS); nothing in the catalog goes from 2D to 3D. This fills that
gap for the case that actually covers most drawings: **prismatic parts** —
a closed 2D profile extruded to a constant thickness (sheet metal, plates,
brackets, gaskets, machined flats).

What it does NOT do: reconstruct a solid from three orthographic views. That is
an open research problem, not something to hide behind a CLI flag. See the
"Scope" section in docs/06-drawing-to-simready.md.

Pipeline inside this script:

    DXF closed loops  ->  outer boundary + holes  ->  triangulated cap
                      ->  extruded watertight prism  ->  USD Mesh
                      ->  rigid body + collider + mass + material

The output is deliberately a plain USD asset, not a conformed one — conformance
is `simready_conform.py`'s job, and keeping them separate means the same
conformance code serves every converter.

Usage:
    python drawing_to_usd.py plate.dxf out/plate --thickness 0.012
    python drawing_to_usd.py plate.dxf out/plate --thickness-map thickness.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


# ── units ─────────────────────────────────────────────────────────────────────
# USD stages here are authored in metres (metersPerUnit = 1). Drawings almost
# never are. Getting this wrong silently produces a part 1000x too large, which
# then "passes" every validator and behaves absurdly in physics — so the unit is
# resolved explicitly and always reported.
DXF_UNITS = {
    0: (None, "unitless"), 1: (0.0254, "in"), 2: (0.3048, "ft"), 4: (0.001, "mm"),
    5: (0.01, "cm"), 6: (1.0, "m"), 8: (2.54e-5, "microinch"), 9: (0.0254 / 1000, "mil"),
    10: (0.9144, "yd"), 11: (1e-10, "angstrom"), 12: (1e-9, "nm"),
    13: (1e-6, "micron"), 14: (0.1, "dm"), 15: (10.0, "dam"),
    16: (100.0, "hm"), 17: (1000.0, "km"),
}


def resolve_scale(doc, override: str | None) -> tuple[float, str]:
    if override:
        for f, n in DXF_UNITS.values():
            if n == override:
                return f, override
        raise SystemExit(f"ERROR: unknown unit '{override}'")
    code = doc.header.get("$INSUNITS", 0)
    factor, name = DXF_UNITS.get(code, (None, "unknown"))
    if factor is None:
        # Unitless drawings are common. mm is the overwhelmingly likely intent
        # for mechanical work, but say so loudly rather than pretending we know.
        print("WARNING: DXF declares no units ($INSUNITS=0); assuming mm. "
              "Override with --units if that is wrong.", file=sys.stderr)
        return 0.001, "mm (assumed)"
    return factor, name


# ── loop extraction ───────────────────────────────────────────────────────────
def _arc_points(cx, cy, r, a0, a1, seg_deg=6.0):
    sweep = (a1 - a0) % 360.0 or 360.0
    n = max(2, int(math.ceil(sweep / seg_deg)) + 1)
    a = np.radians(np.linspace(a0, a0 + sweep, n))
    return np.column_stack([cx + r * np.cos(a), cy + r * np.sin(a)])


def _bulge_points(p0, p1, bulge, seg_deg=6.0):
    """A DXF 'bulge' encodes a circular arc between two vertices."""
    if abs(bulge) < 1e-12:
        return np.array([p0])
    theta = 4.0 * math.atan(bulge)
    chord = np.array(p1) - np.array(p0)
    d = float(np.hypot(*chord))
    if d < 1e-12:
        return np.array([p0])
    r = d / (2.0 * math.sin(abs(theta) / 2.0))
    mid = (np.array(p0) + np.array(p1)) / 2.0
    h = math.sqrt(max(r * r - (d / 2.0) ** 2, 0.0))
    n = np.array([-chord[1], chord[0]]) / d
    c = mid + n * (h if (theta > 0) == (bulge > 0) else -h) * (1 if theta > 0 else -1)
    a0 = math.degrees(math.atan2(p0[1] - c[1], p0[0] - c[0]))
    a1 = a0 + math.degrees(theta)
    pts = _arc_points(c[0], c[1], r, a0, a1 if theta > 0 else a1, seg_deg)
    return pts[:-1] if len(pts) > 1 else pts


def extract_loops(msp, layers: set[str] | None, seg_deg: float) -> list[np.ndarray]:
    """Closed 2D loops, as (N,2) arrays. Only closed profiles can be extruded."""
    loops, skipped = [], []

    def keep(e):
        return layers is None or e.dxf.layer in layers

    for e in msp:
        t = e.dxftype()
        if not keep(e):
            continue
        try:
            if t == "LWPOLYLINE":
                pts = list(e.get_points("xyb"))
                if not e.closed:
                    skipped.append(f"{t} on '{e.dxf.layer}' (open)")
                    continue
                out = []
                for i, (x, y, b) in enumerate(pts):
                    nx, ny, _ = pts[(i + 1) % len(pts)]
                    out.append([x, y])
                    if abs(b) > 1e-12:
                        out.extend(_bulge_points((x, y), (nx, ny), b, seg_deg)[1:])
                loops.append(np.asarray(out, float))
            elif t == "POLYLINE":
                if not e.is_closed:
                    skipped.append(f"{t} on '{e.dxf.layer}' (open)")
                    continue
                loops.append(np.array([[v.dxf.location.x, v.dxf.location.y]
                                       for v in e.vertices], float))
            elif t == "CIRCLE":
                c = e.dxf.center
                loops.append(_arc_points(c.x, c.y, e.dxf.radius, 0.0, 360.0, seg_deg)[:-1])
            elif t in ("LINE", "ARC", "SPLINE", "ELLIPSE"):
                skipped.append(f"{t} on '{e.dxf.layer}' (not a closed loop on its own)")
        except Exception as exc:                       # keep going, report at the end
            skipped.append(f"{t}: {type(exc).__name__}")

    # drop degenerate loops
    clean = []
    for lp in loops:
        if len(lp) >= 3 and float(np.abs(np.diff(lp, axis=0)).max(initial=0)) > 0:
            if np.allclose(lp[0], lp[-1]):
                lp = lp[:-1]
            if len(lp) >= 3:
                clean.append(lp)
    return clean, skipped


# ── outer vs holes ────────────────────────────────────────────────────────────
def signed_area(p: np.ndarray) -> float:
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def point_in_poly(pt, poly) -> bool:
    x, y = pt
    xs, ys = poly[:, 0], poly[:, 1]
    xj, yj = np.roll(xs, 1), np.roll(ys, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cross = ((ys > y) != (yj > y)) & (x < (xj - xs) * (y - ys) / (yj - ys + 1e-30) + xs)
    return bool(cross.sum() % 2)


def classify(loops):
    """Largest-area loop is the boundary; loops inside it are holes.

    Nested solids (an island inside a hole) are not handled — they would need a
    full even-odd depth walk, and no test drawing here exercises it. Anything
    that is neither the boundary nor inside it is reported, not silently dropped.
    """
    if not loops:
        return None, [], []
    areas = [abs(signed_area(lp)) for lp in loops]
    oi = int(np.argmax(areas))
    outer = loops[oi]
    holes, outside = [], []
    for i, lp in enumerate(loops):
        if i == oi:
            continue
        (holes if point_in_poly(lp.mean(axis=0), outer) else outside).append(lp)
    return outer, holes, outside


# ── extrusion ─────────────────────────────────────────────────────────────────
def extrude(outer, holes, thickness, z0=0.0):
    """Watertight prism: triangulated caps + quad side walls per loop.

    Winding is set so every face points out of the solid — collision cooking and
    the renderer both care, and a flipped cap is invisible until physics behaves
    strangely.
    """
    import mapbox_earcut as earcut

    # Normalise orientation before anything else. DXF authors loops in whatever
    # direction the drafter happened to draw them, and the cap and wall winding
    # below both assume outer = CCW, holes = CW. Skip this and the solid renders
    # with inside-out faces — ManifoldChecker calls it "face winding is not
    # consistent", and collision cooking can misjudge the interior.
    outer = np.asarray(outer, float)
    if signed_area(outer) < 0:
        outer = outer[::-1]
    fixed_holes = []
    for h in holes:
        h = np.asarray(h, float)
        fixed_holes.append(h[::-1] if signed_area(h) > 0 else h)
    holes = fixed_holes

    loops = [outer] + holes
    # earcut wants a flat vertex list plus the end index of each ring
    verts2d = np.concatenate(loops, axis=0)
    rings = np.cumsum([len(l) for l in loops]).astype(np.uint32)
    tris = earcut.triangulate_float64(verts2d, rings).reshape(-1, 3)
    if len(tris) == 0:
        raise SystemExit("ERROR: triangulation produced no faces — check the profile is closed")

    n = len(verts2d)
    z1 = z0 + thickness
    pts = np.vstack([
        np.column_stack([verts2d, np.full(n, z0)]),   # 0..n-1   bottom
        np.column_stack([verts2d, np.full(n, z1)]),   # n..2n-1  top
    ])

    faces, counts = [], []
    for a, b, c in tris:                                # bottom cap, faces -Z
        faces += [int(a), int(c), int(b)]; counts.append(3)
    for a, b, c in tris:                                # top cap, faces +Z
        faces += [n + int(a), n + int(b), n + int(c)]; counts.append(3)

    # Side walls. One formula serves every loop: orientation was already
    # normalised above (outer CCW, holes CW), and that stored direction is
    # exactly what makes a hole's wall face into the cavity. Flipping holes a
    # second time here double-reverses them and leaves each hole edge traversed
    # identically by its cap and its wall — which is what "face winding is not
    # consistent" means.
    start = 0
    for loop in loops:
        m = len(loop)
        for i in range(m):
            a = start + i
            b = start + (i + 1) % m
            faces += [a, b, n + b, n + a]; counts.append(4)
        start += m

    return pts, np.asarray(counts, np.int32), np.asarray(faces, np.int32)


def prism_volume(outer, holes, thickness) -> float:
    a = abs(signed_area(outer)) - sum(abs(signed_area(h)) for h in holes)
    return max(a, 0.0) * thickness


# ── USD authoring ─────────────────────────────────────────────────────────────
def face_normals(pts, counts, indices):
    """Flat per-face normals via Newell's method.

    Authored explicitly because the solid uses `subdivisionScheme = none` — with
    no subdivision and no normals, NormalsExistChecker fails and renderers have
    to guess. Newell handles the non-planar quads that fillet walls produce.
    """
    normals, k = [], 0
    for c in counts:
        f = indices[k:k + c]; k += c
        v = pts[f]
        nx = ny = nz = 0.0
        for i in range(c):
            a, b = v[i], v[(i + 1) % c]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        n = np.array([nx, ny, nz], float)
        ln = float(np.linalg.norm(n))
        n = n / ln if ln > 1e-20 else np.array([0.0, 0.0, 1.0])
        normals.extend([n] * c)          # faceVarying: one per face-vertex
    return np.asarray(normals, float)


def author_usd(out_path: Path, name, pts, counts, indices, *, volume,
               density, provenance) -> dict:
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Gf, Sdf, Vt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(out_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetMetadata("kilogramsPerUnit", 1.0)

    root = UsdGeom.Xform.Define(stage, f"/{name}")
    root.GetPrim().SetAssetInfoByKey("name", name)
    Usd.ModelAPI(root).SetKind("component")
    stage.SetDefaultPrim(root.GetPrim())

    # typed grouping prims — an untyped prim fails TypeChecker
    UsdGeom.Scope.Define(stage, f"/{name}/Geometry")
    UsdGeom.Scope.Define(stage, f"/{name}/Looks")

    mesh = UsdGeom.Mesh.Define(stage, f"/{name}/Geometry/{name}_solid")
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(counts.tolist()))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(indices.tolist()))
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)   # it is a machined solid
    nrm = face_normals(pts, counts, indices)
    na = mesh.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(*n) for n in nrm]))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*lo), Gf.Vec3f(*hi)]))

    # physics: dynamic rigid body with a convex-hull-friendly mesh collider
    body = UsdPhysics.RigidBodyAPI.Apply(mesh.GetPrim())
    body.CreateRigidBodyEnabledAttr(True)
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    mass_api = UsdPhysics.MassAPI.Apply(mesh.GetPrim())
    mass = volume * density
    mass_api.CreateMassAttr(float(mass))
    mass_api.CreateDensityAttr(float(density))

    scene = UsdPhysics.Scene.Define(stage, f"/{name}/PhysicsScene")
    scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
    scene.CreateGravityMagnitudeAttr(9.81)

    # a visual material, so VM.MAT.001 is satisfied before conformance runs
    mat = UsdShade.Material.Define(stage, f"/{name}/Looks/DrawingMaterial")
    shader = UsdShade.Shader.Define(stage, f"/{name}/Looks/DrawingMaterial/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.62, 0.64, 0.67))
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.9)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.42)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim())
    UsdShade.MaterialBindingAPI(mesh.GetPrim()).Bind(mat)

    layer = stage.GetRootLayer()
    cld = dict(layer.customLayerData)
    cld["DrawingProvenance"] = provenance
    layer.customLayerData = cld
    layer.Save()

    return {"prim": f"/{name}", "mesh": str(mesh.GetPath()),
            "points": len(pts), "faces": len(counts),
            "mass_kg": round(mass, 6), "density_kg_m3": density,
            "bbox_min": [round(float(v), 6) for v in lo],
            "bbox_max": [round(float(v), 6) for v in hi]}


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf", help="input DXF drawing")
    ap.add_argument("outdir", help="output directory")
    ap.add_argument("--name", default=None, help="asset name (default: DXF stem)")
    ap.add_argument("--thickness", type=float, default=None,
                    help="extrusion depth in METRES (e.g. 0.012 for 12 mm)")
    ap.add_argument("--thickness-map", default=None,
                    help="JSON {layer: metres} — extrude each layer separately")
    ap.add_argument("--layers", default=None,
                    help="comma-separated layers to read (default: all)")
    ap.add_argument("--units", default=None,
                    help="override drawing units: mm, cm, m, in, ft")
    ap.add_argument("--density", type=float, default=7850.0,
                    help="kg/m3 for mass (default 7850 = steel)")
    ap.add_argument("--arc-segment-deg", type=float, default=6.0,
                    help="arc tessellation step in degrees (default 6)")
    ap.add_argument("--report", default=None, help="write a JSON report here")
    args = ap.parse_args()

    import ezdxf

    src = Path(args.dxf).resolve()
    name = args.name or src.stem
    doc = ezdxf.readfile(str(src))
    msp = doc.modelspace()

    scale, unit_name = resolve_scale(doc, args.units)
    layers = set(s.strip() for s in args.layers.split(",")) if args.layers else None

    loops, skipped = extract_loops(msp, layers, args.arc_segment_deg)
    if not loops:
        print("ERROR: no closed profiles found. drawing_to_usd extrudes closed "
              "loops (LWPOLYLINE/POLYLINE/CIRCLE); open geometry is ignored.",
              file=sys.stderr)
        if skipped:
            print("  skipped: " + "; ".join(sorted(set(skipped))[:8]), file=sys.stderr)
        return 2

    loops = [lp * scale for lp in loops]                 # into metres
    outer, holes, outside = classify(loops)

    if args.thickness is None and args.thickness_map is None:
        print("ERROR: give --thickness (metres) or --thickness-map.", file=sys.stderr)
        return 2
    thickness = args.thickness
    if args.thickness_map:
        tm = json.loads(Path(args.thickness_map).read_text())
        thickness = float(next(iter(tm.values())))       # single-body case
    if thickness <= 0:
        print("ERROR: --thickness must be > 0", file=sys.stderr)
        return 2

    pts, counts, indices = extrude(outer, holes, thickness)
    volume = prism_volume(outer, holes, thickness)

    outdir = Path(args.outdir).resolve()
    # Crate, not ASCII: a tessellated solid carries thousands of floats, and
    # UsdAsciiPerformanceChecker fails any .usda holding arrays this large.
    usd_path = outdir / f"{name}.usdc"
    provenance = {
        "source_drawing": str(src), "drawing_units": unit_name,
        "unit_scale_to_m": scale, "extrusion_thickness_m": thickness,
        "profile_loops": len(loops), "holes": len(holes),
        "arc_segment_deg": args.arc_segment_deg,
    }
    info = author_usd(usd_path, name, pts, counts, indices,
                      volume=volume, density=args.density, provenance=provenance)

    report = {"input": str(src), "output_usd": str(usd_path),
              "units": unit_name, "unit_scale_to_m": scale,
              "thickness_m": thickness, "loops": len(loops),
              "outer_loop_points": len(outer), "holes": len(holes),
              "loops_outside_boundary": len(outside),
              "volume_m3": round(volume, 9), **info,
              "ignored_entities": sorted(set(skipped))}

    if outside:
        print(f"WARNING: {len(outside)} loop(s) lie outside the boundary and were "
              "not treated as holes — separate parts are not yet supported.",
              file=sys.stderr)

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
