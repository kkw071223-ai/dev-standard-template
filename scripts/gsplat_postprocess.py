#!/usr/bin/env python3
"""
gsplat_postprocess.py — make `usd-convert-gsplat` output survive validation.

Run this on every NuRec / 3DGS reconstruction before it enters an asset pipeline.

`usd-convert-gsplat` emits a valid Gaussian-splat prim but fails
`nvidia_usd_validate` on two counts (both reproduced, see
docs/02-verified-findings.md §6):

  ByteAlignmentChecker  File 'default.usda' in package has an invalid offset 42.
                        -> USDZ requires 64-byte alignment; write .usdc instead.
  DefaultPrimChecker    The default prim <name> of type
                        "ParticleField3DGaussianSplat" is not Xformable nor Scope.
                        -> reference it under a /World Xform and default to that.

The second one is not paperwork: a default prim that is not Xformable cannot be
placed, aligned or instanced in a larger scene, which is the whole point of
converting a reconstruction to USD.

Verified result: 2 failures -> 0 failures.

Usage:
    python gsplat_postprocess.py splat.usdc out/scene.usdc
    python gsplat_postprocess.py splat.usdz out/scene.usdc --root /World --up-axis Z
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from pxr import Usd, UsdGeom, Sdf


GSPLAT_TYPE = "ParticleField3DGaussianSplat"


def find_splat_prims(stage: Usd.Stage) -> list[Usd.Prim]:
    return [p for p in stage.Traverse() if p.GetTypeName() == GSPLAT_TYPE]


def postprocess(src: Path, dst: Path, root: str = "/World",
                up_axis: str = "Z", meters_per_unit: float = 1.0) -> dict:
    src_stage = Usd.Stage.Open(str(src))
    if not src_stage:
        raise SystemExit(f"ERROR: cannot open {src}")

    splats = find_splat_prims(src_stage)
    if not splats:
        raise SystemExit(f"ERROR: no {GSPLAT_TYPE} prim found in {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    # The payload must be a sibling .usdc: .usdz re-triggers ByteAlignmentChecker.
    payload = dst.parent / f"{dst.stem}_splat.usdc"
    if src.suffix == ".usdz":
        # repack the package contents into a plain crate layer
        flat = src_stage.Flatten()
        flat.Export(str(payload))
    elif src.resolve() != payload.resolve():
        shutil.copy(src, payload)

    out = Usd.Stage.CreateNew(str(dst))
    UsdGeom.SetStageUpAxis(
        out, UsdGeom.Tokens.z if up_axis.upper() == "Z" else UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(out, meters_per_unit)

    world = UsdGeom.Xform.Define(out, root)
    out.SetDefaultPrim(world.GetPrim())

    referenced = []
    for sp in splats:
        target = f"{root}/{sp.GetName()}"
        prim = out.OverridePrim(target)
        prim.GetReferences().AddReference(f"./{payload.name}", sp.GetPath())
        referenced.append(target)

    out.GetRootLayer().Save()

    return {
        "input": str(src),
        "output": str(dst),
        "payload": str(payload),
        "root_xform": root,
        "splat_prims": referenced,
        "up_axis": up_axis,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="usd-convert-gsplat output (.usdc/.usda/.usdz)")
    ap.add_argument("output", help="validator-clean .usdc to write")
    ap.add_argument("--root", default="/World", help="Xform root prim path")
    ap.add_argument("--up-axis", default="Z", choices=["Y", "Z"])
    ap.add_argument("--meters-per-unit", type=float, default=1.0)
    args = ap.parse_args()

    out_path = Path(args.output)
    if out_path.suffix == ".usdz":
        print("ERROR: .usdz output re-triggers ByteAlignmentChecker; use .usdc",
              file=sys.stderr)
        return 2

    import json
    report = postprocess(Path(args.input), out_path, args.root,
                         args.up_axis, args.meters_per_unit)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
