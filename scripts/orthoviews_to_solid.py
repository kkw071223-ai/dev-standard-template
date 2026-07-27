#!/usr/bin/env python3
"""
orthoviews_to_solid.py — reconstruct a 3D solid from orthographic views in a DXF.

This is the reconstruction step, not a format conversion. Given two or three
views of the same subject (plan, front elevation, side elevation), it recovers
the solid by shape-from-silhouette:

    1. rasterise each view's line work into a filled silhouette mask
    2. carve a voxel grid — a voxel survives only where EVERY view says
       "occupied" at its projection
    3. surface the survivors with marching cubes and write a USD mesh

What this recovers is the **visual hull**: the tightest solid consistent with
every silhouette you supply. For prismatic and blocky subjects that is the
object. For anything with concavities hidden from all given views, the hull is
larger than the truth — a bowl comes back as a cylinder. Two views leave one
axis unconstrained and give an envelope; three constrain it properly.

So this reconstructs an object's **outer envelope**, which is what layout,
reach, clash and footprint work actually need. It does not recover internals,
and on an assembly drawing it recovers the assembly's envelope rather than its
parts.

    # verify the algorithm on a shape whose answer is known
    python orthoviews_to_solid.py --self-test

    # reconstruct from a drawing
    python orthoviews_to_solid.py plant.dxf out/ --name skid --units mm \
        --view plan  1296 8500 3376 11704 \
        --view front 3242 8489 7032 11715 \
        --resolution 220
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawing_to_usd import resolve_scale  # noqa: E402
from drawing_set_to_usd import walk       # noqa: E402


# view name -> (horizontal axis, vertical axis) of the 3D frame it constrains.
# X right, Y depth, Z up.
VIEW_AXES = {
    "plan":  (0, 1),   # looking down  -> constrains X and Y
    "top":   (0, 1),
    "front": (0, 2),   # looking along -Y -> constrains X and Z
    "side":  (1, 2),   # looking along  X -> constrains Y and Z
    "right": (1, 2),
    "left":  (1, 2),
}


def rasterize(polys, window, res, close_px=3):
    """Line work -> filled silhouette mask.

    Drawn outlines are hollow, so the strokes are rasterised, morphologically
    closed to bridge the gaps left by dimension breaks and centre lines, then
    hole-filled. Without the closing step a profile that is 2 px short of
    meeting stays open and the fill leaks over the whole view.
    """
    from skimage.draw import line as skline
    from skimage.morphology import closing, disk
    from scipy.ndimage import binary_fill_holes

    x0, y0, x1, y1 = window
    w = max(x1 - x0, 1e-9)
    h = max(y1 - y0, 1e-9)
    nx = int(res)
    ny = max(2, int(round(res * h / w)))
    mask = np.zeros((ny, nx), bool)

    for p in polys:
        q = np.asarray(p, float)
        c = np.clip(((q[:, 0] - x0) / w * (nx - 1)).round().astype(int), 0, nx - 1)
        r = np.clip(((y1 - q[:, 1]) / h * (ny - 1)).round().astype(int), 0, ny - 1)
        for i in range(len(q) - 1):
            rr, cc = skline(r[i], c[i], r[i + 1], c[i + 1])
            mask[rr, cc] = True

    if close_px > 0:
        mask = closing(mask, disk(close_px))
    filled = binary_fill_holes(mask)
    return filled if filled is not None else mask


def carve(masks, res_xyz):
    """Intersect the silhouettes into an occupancy grid."""
    nx, ny, nz = res_xyz
    vol = np.ones((nx, ny, nz), bool)
    for axes, m in masks:
        ha, va = axes
        mh = m.shape[1]
        mv = m.shape[0]
        # sample the mask at each voxel's projected position
        idx = [np.arange(n) for n in (nx, ny, nz)]
        H = (idx[ha] / max(nx if ha == 0 else (ny if ha == 1 else nz) - 1, 1))
        V = (idx[va] / max(nx if va == 0 else (ny if va == 1 else nz) - 1, 1))
        hcol = np.clip((H * (mh - 1)).round().astype(int), 0, mh - 1)
        vrow = np.clip(((1.0 - V) * (mv - 1)).round().astype(int), 0, mv - 1)
        plane = m[np.ix_(vrow, hcol)]          # (len(va), len(ha))
        # broadcast that plane across the third axis
        third = ({0, 1, 2} - {ha, va}).pop()
        shp = [1, 1, 1]
        shp[ha] = plane.shape[1]
        shp[va] = plane.shape[0]
        block = np.moveaxis(plane, (0, 1), (1, 0)) if ha > va else plane
        vol &= np.broadcast_to(block.reshape(shp), (nx, ny, nz))
    return vol


def mesh_from_volume(vol, origin, spacing, step=1):
    """Surface the occupancy grid. `step` > 1 coarsens marching cubes, which is
    the cheapest way to keep the triangle count sane — a binary grid otherwise
    yields roughly two triangles per surface voxel face."""
    from skimage.measure import marching_cubes
    padded = np.pad(vol.astype(np.float32), 1)
    verts, faces, normals, _ = marching_cubes(padded, level=0.5, spacing=spacing,
                                              step_size=max(1, int(step)))
    verts = verts - np.asarray(spacing, float)      # undo the pad
    verts = verts + np.asarray(origin, float)
    # marching cubes already gives per-vertex normals; authoring them keeps
    # NormalsExistChecker happy and saves the renderer guessing on a mesh with
    # subdivisionScheme = none
    return verts, faces, normals


def self_test() -> int:
    """Reconstruct an L-block whose true volume is known, and check the number."""
    print("self-test — L-shaped block, 100 x 60 x 40 mm with a 40 x 30 x 40 notch")
    L, W, H = 0.100, 0.060, 0.040
    nx = 0.040, 0.030                     # notch across X, Y (full depth in Z)

    def rect(x0, y0, x1, y1):
        return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]], float)

    # plan (X-Y): the L footprint
    plan = [np.array([[0, 0], [L, 0], [L, W - nx[1]], [L - nx[0], W - nx[1]],
                      [L - nx[0], W], [0, W], [0, 0]], float)]
    # front (X-Z): full rectangle
    front = [rect(0, 0, L, H)]
    # side (Y-Z): full rectangle
    side = [rect(0, 0, W, H)]

    res = 200
    masks = [
        (VIEW_AXES["plan"],  rasterize(plan,  (0, 0, L, W), res, close_px=1)),
        (VIEW_AXES["front"], rasterize(front, (0, 0, L, H), res, close_px=1)),
        (VIEW_AXES["side"],  rasterize(side,  (0, 0, W, H), res, close_px=1)),
    ]
    n = (res, max(2, int(res * W / L)), max(2, int(res * H / L)))
    vol = carve(masks, n)
    sp = (L / n[0], W / n[1], H / n[2])
    got = float(vol.sum()) * sp[0] * sp[1] * sp[2]
    want = L * W * H - nx[0] * nx[1] * H
    err = abs(got - want) / want
    print(f"  voxels occupied : {int(vol.sum())} of {vol.size}")
    print(f"  reconstructed   : {got*1e6:8.2f} cm3")
    print(f"  true volume     : {want*1e6:8.2f} cm3")
    print(f"  error           : {err:.2%}")
    verts, faces, _ = mesh_from_volume(vol, (0, 0, 0), sp)
    print(f"  surfaced        : {len(verts)} verts / {len(faces)} triangles")
    ok = err < 0.03 and len(faces) > 0
    print("  RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf", nargs="?")
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--name", default="reconstructed")
    ap.add_argument("--units", default=None)
    ap.add_argument("--layers", default=None)
    ap.add_argument("--view", action="append", nargs=5,
                    metavar=("KIND", "X0", "Y0", "X1", "Y1"),
                    help="view window in drawing units; KIND = plan|front|side")
    ap.add_argument("--resolution", type=int, default=200,
                    help="voxels across the longest axis (default 200)")
    ap.add_argument("--mesh-step", type=int, default=2,
                    help="marching-cubes stride; 2 quarters the triangle count")
    ap.add_argument("--close-px", type=int, default=3,
                    help="morphological closing radius when filling outlines")
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not (args.dxf and args.outdir and args.view):
        ap.error("give a dxf, an outdir and at least two --view windows "
                 "(or use --self-test)")

    import ezdxf
    from pxr import Usd, UsdGeom, Gf, Vt

    src = Path(args.dxf).resolve()
    doc = ezdxf.readfile(str(src))
    msp = doc.modelspace()
    scale, unit_name = resolve_scale(doc, args.units)
    keep = set(s.strip() for s in args.layers.split(",")) if args.layers else None

    print(f"reading {src.name} (units {unit_name})")
    geom = [(layer, pts) for layer, pts, _ in walk(msp, 8.0)
            if not keep or layer in keep]
    print(f"  {len(geom)} polylines")

    # ── build one silhouette per view
    views, extents = [], {}
    for kind, x0, y0, x1, y1 in args.view:
        kind = kind.lower()
        if kind not in VIEW_AXES:
            ap.error(f"unknown view kind '{kind}'; use plan|top|front|side|right|left")
        win = tuple(float(v) for v in (x0, y0, x1, y1))
        inside = [p for _, p in geom
                  if (p[:, 0] >= win[0]).any() and (p[:, 0] <= win[2]).any()
                  and (p[:, 1] >= win[1]).any() and (p[:, 1] <= win[3]).any()
                  and p[:, 0].mean() >= win[0] and p[:, 0].mean() <= win[2]
                  and p[:, 1].mean() >= win[1] and p[:, 1].mean() <= win[3]]
        m = rasterize(inside, win, args.resolution, args.close_px)
        frac = m.mean()
        ha, va = VIEW_AXES[kind]
        extents[ha] = max(extents.get(ha, 0.0), (win[2] - win[0]) * scale)
        extents[va] = max(extents.get(va, 0.0), (win[3] - win[1]) * scale)
        views.append((VIEW_AXES[kind], m))
        print(f"  view {kind:<6} {len(inside):>6} polylines, mask {m.shape[1]}x{m.shape[0]}, "
              f"{frac:6.1%} filled")
        if frac > 0.92:
            print("      WARNING: silhouette is almost solid — the window probably "
                  "includes the sheet frame or a table")
        if frac < 0.01:
            print("      WARNING: silhouette nearly empty — check the window")

    if len(views) < 2:
        print("ERROR: need at least two views", file=sys.stderr)
        return 2
    for ax in (0, 1, 2):
        extents.setdefault(ax, max(extents.values()))

    # ── carve
    span = [extents[0], extents[1], extents[2]]
    longest = max(span)
    n = tuple(max(4, int(round(args.resolution * s / longest))) for s in span)
    print(f"  voxel grid {n[0]} x {n[1]} x {n[2]} "
          f"({np.prod(n)/1e6:.1f} M) over {span[0]:.2f} x {span[1]:.2f} x {span[2]:.2f} m")
    vol = carve(views, n)
    occ = int(vol.sum())
    sp = (span[0] / n[0], span[1] / n[1], span[2] / n[2])
    volume = occ * sp[0] * sp[1] * sp[2]
    print(f"  occupied {occ} voxels -> {volume:.4f} m3 "
          f"({occ/vol.size:.1%} of the box)")
    if occ == 0:
        print("ERROR: nothing survived the intersection — check view windows and axes",
              file=sys.stderr)
        return 2

    verts, faces, normals = mesh_from_volume(vol, (0.0, 0.0, 0.0), sp, args.mesh_step)
    print(f"  surfaced {len(verts)} verts / {len(faces)} triangles")

    # ── USD
    outdir = Path(args.outdir).resolve() / args.name
    outdir.mkdir(parents=True, exist_ok=True)
    usd_path = outdir / f"{args.name}.usd"
    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, f"/{args.name}")
    Usd.ModelAPI(root).SetKind("component")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.Scope.Define(stage, f"/{args.name}/Geometry")
    m = UsdGeom.Mesh.Define(stage, f"/{args.name}/Geometry/{args.name}_hull")
    m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, v)) for v in verts]))
    m.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(faces)))
    m.CreateFaceVertexIndicesAttr(Vt.IntArray([int(i) for f in faces for i in f]))
    m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    # normals are per-vertex and the indices address the same array
    # marching cubes points into the solid, and occasionally emits a
    # zero-length normal on a degenerate cell — NormalsValidChecker rejects
    # those, so normalise and substitute a unit vector where the length is nil
    nrm = -np.asarray(normals, float)
    ln = np.linalg.norm(nrm, axis=1)
    bad = ln < 1e-9
    nrm[~bad] /= ln[~bad, None]
    if bad.any():
        nrm[bad] = (0.0, 0.0, 1.0)
        print(f"  replaced {int(bad.sum())} degenerate normal(s)")
    m.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, v)) for v in nrm]))
    m.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    m.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*verts.min(axis=0)),
                                      Gf.Vec3f(*verts.max(axis=0))]))
    m.CreateDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.55, 0.6, 0.68)]))

    lay = stage.GetRootLayer()
    cld = dict(lay.customLayerData)
    cld["DrawingProvenance"] = {
        "source_drawing": str(src), "drawing_units": unit_name,
        "method": "shape-from-silhouette (visual hull) over orthographic views",
        "views": ", ".join(v[0] for v in args.view),
        "voxel_grid": "x".join(str(v) for v in n),
        "volume_m3": round(volume, 6),
        "note": "Outer envelope consistent with the supplied views. Concavities "
                "hidden from all views are not recovered.",
    }
    lay.customLayerData = cld
    lay.Save()

    report = {"input": str(src), "output_usd": str(usd_path), "units": unit_name,
              "views": [{"kind": v[0], "window": [float(x) for x in v[1:]]}
                        for v in args.view],
              "voxel_grid": list(n), "occupied": occ, "volume_m3": volume,
              "bbox_m": {"size": [round(float(v), 4)
                                  for v in (verts.max(axis=0) - verts.min(axis=0))]},
              "vertices": len(verts), "triangles": len(faces)}
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
    print(f"\nwrote {usd_path}  ({usd_path.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
