#!/usr/bin/env python3
"""
simready_conform.py — Close the gap between a converted USD asset and a
SimReady Foundation profile.

Input : a USD asset produced by urdf_usd_converter / mujoco_usd_converter
Output: a flattened, SimReady-conformant asset tree + a JSON change report

Fixes applied (requirement codes from NVIDIA SimReady Foundation):
  NP.005  asset_folder/intermediate/asset.usda, single USD layer
  NP.006  SimReady_Metadata in root layer customLayerData
  RB.006  resetXformStack on rigid bodies nested under rigid bodies
  GSP.001 grasp_identifier BasisCurves with >= 2 points
  PMT.001 physics material bound on every collision prim
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Gf, Sdf


def _is_dynamic_rigid_body(prim: Usd.Prim) -> bool:
    rb = UsdPhysics.RigidBodyAPI(prim)
    if not rb:
        return False
    enabled = rb.GetRigidBodyEnabledAttr().Get()
    if enabled is False:
        return False
    kin = UsdPhysics.RigidBodyAPI(prim).GetKinematicEnabledAttr().Get()
    return not bool(kin)


def fix_nested_rigid_bodies(stage: Usd.Stage) -> list[str]:
    """RB.006 — a rigid body under another rigid body needs an xformstack reset.

    The validator clears a prim only when that prim *itself* carries the reset:
    an ancestor's reset does not cover its descendants. So every dynamic rigid
    body with any dynamic rigid-body ancestor gets its own reset.
    """
    changed = []
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return changed
    for prim in Usd.PrimRange(default_prim):
        if not _is_dynamic_rigid_body(prim):
            continue
        parent = prim.GetParent()
        nested = False
        while parent and parent != stage.GetPseudoRoot():
            if _is_dynamic_rigid_body(parent):
                nested = True
                break
            parent = parent.GetParent()
        if nested:
            xform = UsdGeom.Xformable(prim)
            if xform and not xform.GetResetXformStack():
                xform.SetResetXformStack(True)
                changed.append(str(prim.GetPath()))
    return changed


def add_grasp_vector(stage: Usd.Stage, grasp_prim_path: str | None = None) -> str | None:
    """GSP.001 — at least one BasisCurves named grasp_identifier* with >=2 points."""
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return None
    for prim in Usd.PrimRange(default_prim):
        if prim.GetTypeName() == "BasisCurves" and prim.GetName().startswith("grasp_identifier"):
            return None  # already conformant

    # Derive a grasp axis from the asset's bounding box.
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    rng = bbox_cache.ComputeWorldBound(default_prim).ComputeAlignedRange()
    if rng.IsEmpty():
        lo, hi = Gf.Vec3f(0, 0, 0), Gf.Vec3f(0, 0, 0.1)
    else:
        mn, mx = rng.GetMin(), rng.GetMax()
        mid_x = (mn[0] + mx[0]) / 2.0
        mid_y = (mn[1] + mx[1]) / 2.0
        top = mx[2]
        lo = Gf.Vec3f(mid_x, mid_y, top)
        hi = Gf.Vec3f(mid_x, mid_y, top + max(0.02, (mx[2] - mn[2]) * 0.1))

    path = grasp_prim_path or f"{default_prim.GetPath()}/grasp_identifier_0"
    curves = UsdGeom.BasisCurves.Define(stage, path)
    curves.CreateTypeAttr().Set(UsdGeom.Tokens.linear)
    curves.CreateCurveVertexCountsAttr().Set([2])
    curves.CreatePointsAttr().Set([lo, hi])
    curves.CreateWidthsAttr().Set([0.005, 0.005])
    curves.CreateExtentAttr().Set([lo, hi])
    UsdGeom.Imageable(curves).CreatePurposeAttr().Set(UsdGeom.Tokens.guide)
    return path


def bind_physics_materials(stage: Usd.Stage, static_friction=0.7,
                           dynamic_friction=0.5, restitution=0.1) -> tuple[str | None, list[str]]:
    """PMT.001 — every collider needs material:binding:physics."""
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return None, []

    colliders = [p for p in Usd.PrimRange(default_prim)
                 if p.HasAPI(UsdPhysics.CollisionAPI)]
    unbound = []
    for p in colliders:
        binding_api = UsdShade.MaterialBindingAPI(p)
        rel = binding_api.GetDirectBindingRel("physics")
        if not rel or not rel.GetTargets():
            unbound.append(p)
    if not unbound:
        return None, []

    mat_path = f"{default_prim.GetPath()}/PhysicsMaterials/DefaultPhysicsMaterial"
    material = UsdShade.Material.Define(stage, mat_path)
    phys_mat = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    phys_mat.CreateStaticFrictionAttr().Set(static_friction)
    phys_mat.CreateDynamicFrictionAttr().Set(dynamic_friction)
    phys_mat.CreateRestitutionAttr().Set(restitution)

    bound = []
    for p in unbound:
        UsdShade.MaterialBindingAPI.Apply(p)
        UsdShade.MaterialBindingAPI(p).Bind(
            material,
            bindingStrength=UsdShade.Tokens.weakerThanDescendants,
            materialPurpose="physics",
        )
        bound.append(str(p.GetPath()))
    return mat_path, bound


def bind_visual_materials(stage: Usd.Stage,
                          diffuse=(0.5, 0.5, 0.5)) -> tuple[str | None, list[str]]:
    """VM.MAT.001 — every renderable GPrim needs a computed material binding.

    The MuJoCo converter emits geometry without visual materials; the URDF
    converter emits them from <material> tags. Prims whose computed purpose is
    `guide` or `proxy` are exempt, which is why the grasp curve added for
    GSP.001 does not need one.
    """
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return None, []

    unbound = []
    for prim in Usd.PrimRange(default_prim):
        if not UsdGeom.Gprim(prim):
            continue
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            continue
        if imageable.ComputePurpose() not in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render):
            continue
        binding_api = UsdShade.MaterialBindingAPI(prim)
        if binding_api.GetMaterialBindSubsets():
            continue  # subsets carry their own bindings
        mat, _ = binding_api.ComputeBoundMaterial()
        if not mat:
            unbound.append(prim)

    if not unbound:
        return None, []

    mat_path = f"{default_prim.GetPath()}/Looks/DefaultVisualMaterial"
    material = UsdShade.Material.Define(stage, mat_path)
    shader = UsdShade.Shader.Define(stage, f"{mat_path}/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*diffuse))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    bound = []
    for prim in unbound:
        UsdShade.MaterialBindingAPI.Apply(prim)
        UsdShade.MaterialBindingAPI(prim).Bind(
            material, bindingStrength=UsdShade.Tokens.weakerThanDescendants)
        bound.append(str(prim.GetPath()))
    return mat_path, bound


def stamp_metadata(stage: Usd.Stage, asset_name: str, profile: str,
                   profile_version: str, source_asset: str) -> dict:
    """NP.006 — SimReady_Metadata in root layer customLayerData."""
    meta = {
        "asset_name": asset_name,
        "profile": profile,
        "profile_version": profile_version,
        "source_asset": source_asset,
    }
    layer = stage.GetRootLayer()
    cld = dict(layer.customLayerData)
    cld["SimReady_Metadata"] = meta
    layer.customLayerData = cld
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="input USD asset (interface layer)")
    ap.add_argument("outdir", help="output asset folder (asset_folder/)")
    ap.add_argument("--name", default=None, help="asset name (default: input stem)")
    ap.add_argument("--profile", default="Prop-Robotics-Neutral")
    ap.add_argument("--profile-version", default="1.0.0")
    ap.add_argument("--format", choices=["auto", "usda", "usd"], default="auto",
                    help="output container. 'auto' writes crate-backed .usd when the "
                         "stage holds large arrays, .usda otherwise")
    ap.add_argument("--report", default=None, help="write JSON change report here")
    args = ap.parse_args()

    src = Path(args.input).resolve()
    name = args.name or src.stem

    stage = Usd.Stage.Open(str(src))
    if not stage:
        print(f"ERROR: cannot open {src}", file=sys.stderr)
        return 2

    # NP.005 — flatten the payload/sublayer tree into one layer
    flat = stage.Flatten()
    out_stage = Usd.Stage.Open(flat)

    # Container choice is forced by two validators wanting opposite things:
    #   nvidia_usd_validate   fails a .usda holding large arrays
    #                         (UsdAsciiPerformanceChecker)
    #   simready-validate     only accepts .usd / .usda — it ignores .usdc
    #                         outright (api.py: suffix not in [".usd", ".usda"])
    # `.usd` satisfies both: the extension is accepted, and USD writes it as
    # crate, so the arrays are never ASCII. Plain props stay .usda so they remain
    # readable in a text editor.
    ext = args.format
    if ext == "auto":
        big = any(
            len(v) > 1000
            for p in out_stage.Traverse() for a in p.GetAttributes()
            if a.GetTypeName().isArray and (v := a.Get()) is not None
        )
        ext = "usd" if big else "usda"

    # NP.005 wants asset_folder/intermediate_folder/asset.<ext>
    asset_dir = Path(args.outdir).resolve() / name
    asset_dir.mkdir(parents=True, exist_ok=True)
    dst = asset_dir / f"{name}.{ext}"

    report = {"input": str(src), "output": str(dst), "fixes": {}}

    reset = fix_nested_rigid_bodies(out_stage)
    report["fixes"]["RB.006_resetXformStack"] = reset

    grasp = add_grasp_vector(out_stage)
    report["fixes"]["GSP.001_grasp_vector"] = grasp

    mat, bound = bind_physics_materials(out_stage)
    report["fixes"]["PMT.001_physics_material"] = {"material": mat, "bound_prims": bound}

    vmat, vbound = bind_visual_materials(out_stage)
    report["fixes"]["VM.MAT.001_visual_material"] = {"material": vmat, "bound_prims": vbound}

    meta = stamp_metadata(out_stage, name, args.profile, args.profile_version, str(src))
    report["fixes"]["NP.006_metadata"] = meta

    out_stage.GetRootLayer().Export(str(dst))
    report["fixes"]["NP.005_flattened_to"] = str(dst)

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
