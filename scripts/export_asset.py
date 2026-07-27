#!/usr/bin/env python3
"""
export_asset.py — hand a finished asset over in the formats people actually open.

A conformed asset lives as `.usd` (crate) because that is what both validators
accept, but crate is binary and most people have no USD viewer installed. This
writes the same stage out three ways so it can be inspected, viewed and diffed:

  .usd   crate — the pipeline's own format, what you feed back into the tools
  .usda  ASCII — open it in any text editor and read the physics and materials
  .usdz  package — Quick Look on macOS/iOS opens it with a double-click

Geometry is identical in all three; only the container differs.

    python export_asset.py .out/bracket/conformed/bracket/bracket.usd deliverables/
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def summarize(path: Path) -> dict:
    """Read the written file back and report what is in it — never trust the write."""
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade

    stage = Usd.Stage.Open(str(path))
    if not stage:
        return {"error": f"cannot open {path}"}

    meshes, colliders, bodies, materials = [], [], [], []
    for prim in stage.Traverse():
        if UsdGeom.Mesh(prim):
            m = UsdGeom.Mesh(prim)
            meshes.append({
                "path": str(prim.GetPath()),
                "points": len(m.GetPointsAttr().Get() or []),
                "faces": len(m.GetFaceVertexCountsAttr().Get() or []),
            })
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            colliders.append(str(prim.GetPath()))
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            bodies.append(str(prim.GetPath()))
        if UsdShade.Material(prim):
            materials.append(str(prim.GetPath()))

    bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_,
                                                      UsdGeom.Tokens.render])
    rng = bbox.ComputeWorldBound(stage.GetDefaultPrim()).ComputeAlignedRange()
    size = [round(float(v), 6) for v in (rng.GetMax() - rng.GetMin())] \
        if not rng.IsEmpty() else None

    mass = None
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.MassAPI):
            a = UsdPhysics.MassAPI(prim).GetMassAttr().Get()
            if a:
                mass = round(float(a), 6)
                break

    meta = dict(stage.GetRootLayer().customLayerData)
    return {
        "file": path.name,
        "size_kb": round(path.stat().st_size / 1024, 1),
        "default_prim": str(stage.GetDefaultPrim().GetPath()),
        "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
        "meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage),
        "bbox_size_m": size,
        "mass_kg": mass,
        "meshes": meshes,
        "rigid_bodies": bodies,
        "colliders": colliders,
        "materials": materials,
        "simready_metadata": meta.get("SimReady_Metadata"),
        "drawing_provenance": meta.get("DrawingProvenance"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asset", help="conformed .usd/.usda/.usdc to export")
    ap.add_argument("outdir")
    ap.add_argument("--name", default=None, help="basename (default: input stem)")
    ap.add_argument("--formats", default="usd,usda,usdz",
                    help="comma-separated (default: usd,usda,usdz)")
    args = ap.parse_args()

    from pxr import Usd, UsdUtils

    src = Path(args.asset).resolve()
    name = args.name or src.stem
    root = Path(args.outdir).resolve()

    # NP.005 wants asset_folder/<name>/<name>.usd AND no other .usd/.usda
    # anywhere beneath that folder — the checker walks the whole subtree. So a
    # readable .usda cannot sit beside the crate copy without breaking the
    # conformance the pipeline just established. `.usdz` is fine to colocate:
    # only `.usd` and `.usda` are counted.
    out = root / name                    # conformant: .usd (+ .usdz)
    readable = root / f"{name}-readable"  # .usda lives here instead
    out.mkdir(parents=True, exist_ok=True)
    wanted = [f.strip() for f in args.formats.split(",") if f.strip()]
    if "usda" in wanted:
        readable.mkdir(parents=True, exist_ok=True)

    stage = Usd.Stage.Open(str(src))
    if not stage:
        print(f"ERROR: cannot open {src}")
        return 2
    flat = stage.Flatten()

    written = []
    for ext in wanted:
        dst = (readable if ext == "usda" else out) / f"{name}.{ext}"
        if ext == "usdz":
            # UsdUtils wraps a real layer from disk, and the layer's filename
            # becomes the entry name inside the package — so stage it under the
            # asset's own name in a temp dir rather than a dot-prefixed file.
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / f"{name}.usdc"
                flat.Export(str(tmp))
                ok = UsdUtils.CreateNewUsdzPackage(str(tmp), str(dst))
            if not ok:
                print(f"  WARNING: could not package {dst.name}")
                continue
        else:
            flat.Export(str(dst))
        written.append(dst)

    report = {"source": str(src), "exported": []}
    for p in written:
        info = summarize(p)
        report["exported"].append(info)
        print(f"{p}")
        print(f"    {info['size_kb']} KB · default prim {info['default_prim']} · "
              f"up {info['up_axis']} · {info['meters_per_unit']} m/unit")
        if info.get("bbox_size_m"):
            b = info["bbox_size_m"]
            print(f"    bbox {b[0]*1000:.1f} x {b[1]*1000:.1f} x {b[2]*1000:.1f} mm"
                  + (f" · {info['mass_kg']} kg" if info["mass_kg"] else ""))
        for m in info["meshes"]:
            print(f"    mesh {m['path']}  {m['points']} points / {m['faces']} faces")
        print(f"    {len(info['rigid_bodies'])} rigid body, "
              f"{len(info['colliders'])} collider, {len(info['materials'])} material(s)")

    man = root / f"{name}.manifest.json"      # outside the asset folder on purpose
    man.write_text(json.dumps(report, indent=2))
    print(f"\n{man}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
