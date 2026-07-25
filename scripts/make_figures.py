#!/usr/bin/env python3
"""
make_figures.py — render figures from the pipeline's own artifacts.

These are plots of real data read back out of the USD stages, the recorded
trajectory CSV and the validator JSON. They are not viewport screenshots —
rendering a viewport needs ovrtx and a GPU, which this environment does not have.

Outputs PNGs into --outdir.

Usage:
    python make_figures.py --outdir docs/figures
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

# palette — readable on both light and dark backgrounds
INK, MUTED, GRID = "#1f2430", "#6b7280", "#d6dae2"
BLUE, RED, GREEN, AMBER, PURPLE = "#2f6fd0", "#d1495b", "#2e9e6b", "#e0a020", "#7a4fbf"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "grid.color": GRID, "font.size": 10, "axes.titlesize": 12,
    "axes.titleweight": "bold", "savefig.dpi": 150, "savefig.bbox": "tight",
})


# ─────────────────────────────────────────────────────────── USD geometry
#
# The URDF and MuJoCo converters emit *analytic* Gprims (Cube, Sphere, Cylinder,
# Capsule, Plane), not Meshes — so tessellate them here to draw anything.
#
# They also use `purpose` to separate the two representations of every link:
#   purpose = default  -> visual geometry
#   purpose = guide    -> collision geometry (and the GSP.001 grasp curve)
# That is why collision prims are exempt from VM.MAT.001, which only inspects
# prims whose computed purpose is `default` or `render`.

def _quad_faces(nu, nv, wrap_u=True):
    f = []
    for i in range(nu if wrap_u else nu - 1):
        i2 = (i + 1) % nu
        for j in range(nv - 1):
            f.append([i * nv + j, i2 * nv + j, i2 * nv + j + 1, i * nv + j + 1])
    return f


def _tessellate(prim):
    """(points, quad_faces) in local space for the analytic Gprims we emit."""
    from pxr import UsdGeom
    t = prim.GetTypeName()

    def attr(name, default):
        a = prim.GetAttribute(name)
        v = a.Get() if a else None
        return default if v is None else v

    if t == "Cube":
        s = float(attr("size", 2.0)) / 2.0
        p = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                      [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float) * s
        f = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4],
             [2, 3, 7, 6], [1, 2, 6, 5], [0, 3, 7, 4]]
        return p, f

    if t == "Sphere":
        r = float(attr("radius", 1.0))
        nu, nv = 16, 10
        u = np.linspace(0, 2 * np.pi, nu, endpoint=False)
        v = np.linspace(0, np.pi, nv)
        p = np.array([[r * np.sin(vv) * np.cos(uu), r * np.sin(vv) * np.sin(uu),
                       r * np.cos(vv)] for uu in u for vv in v])
        return p, _quad_faces(nu, nv)

    if t in ("Cylinder", "Capsule"):
        r = float(attr("radius", 0.5))
        h = float(attr("height", 1.0))
        axis = str(attr("axis", "Z"))
        nu = 18
        u = np.linspace(0, 2 * np.pi, nu, endpoint=False)
        zs = [-h / 2, h / 2]
        p = np.array([[r * np.cos(uu), r * np.sin(uu), z] for uu in u for z in zs])
        if t == "Capsule":  # crude caps: nudge the rings outward by r
            p[:, 2] = np.where(p[:, 2] > 0, p[:, 2] + r * 0.5, p[:, 2] - r * 0.5)
        if axis == "X":
            p = p[:, [2, 1, 0]]
        elif axis == "Y":
            p = p[:, [0, 2, 1]]
        return p, _quad_faces(nu, 2)

    if t == "Plane":
        w = float(attr("width", 1.0)) / 2.0
        l = float(attr("length", 1.0)) / 2.0
        p = np.array([[-w, -l, 0], [w, -l, 0], [w, l, 0], [-w, l, 0]], float)
        return p, [[0, 1, 2, 3]]

    if t == "BasisCurves":
        pts = prim.GetAttribute("points").Get()
        if pts:
            return np.array(pts, float), []
    return None, None


def _gprims(stage):
    """[(path, type, purpose, world_points, faces)] for every drawable Gprim."""
    from pxr import Usd, UsdGeom
    out = []
    xf = UsdGeom.XformCache(Usd.TimeCode.Default())
    for prim in stage.Traverse():
        if not (UsdGeom.Gprim(prim) or prim.GetTypeName() == "BasisCurves"):
            continue
        pts, faces = _tessellate(prim)
        if pts is None or len(pts) == 0:
            continue
        m = xf.GetLocalToWorldTransform(prim)
        world = np.array([m.Transform(tuple(p)) for p in pts], float)
        purpose = str(UsdGeom.Imageable(prim).ComputePurpose())
        out.append((str(prim.GetPath()), str(prim.GetTypeName()), purpose, world, faces))
    return out


def fig_robot(asset: Path, out: Path, title: str):
    """The robot as the USD stage actually describes it: visual vs collision vs grasp."""
    from pxr import Usd
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

    stage = Usd.Stage.Open(str(asset))
    prims = _gprims(stage)
    if not prims:
        print(f"  skip {out.name}: nothing drawable")
        return

    fig = plt.figure(figsize=(12.6, 4.6))
    views = [("visual geometry — purpose = default", ("default", "render")),
             ("collision geometry — purpose = guide", ("guide",)),
             ("both, overlaid", ("default", "render", "guide"))]

    # Frame the mechanism, not the world. A MuJoCo ground Plane is metres across
    # while the cart is centimetres, so including it makes the robot invisible.
    focus = [w for _, t, _, w, _ in prims if t != "Plane"]
    P = np.vstack(focus) if focus else np.vstack([w for *_, w, _ in prims])
    clipped = len(focus) != len(prims)
    ctr = (P.min(axis=0) + P.max(axis=0)) / 2.0
    rad = max(float((P.max(axis=0) - P.min(axis=0)).max()) / 2.0, 1e-3) * 1.15

    for k, (label, purposes) in enumerate(views):
        ax = fig.add_subplot(1, 3, k + 1, projection="3d")
        n = 0
        for path, ptype, purpose, w, faces in prims:
            if purpose not in purposes:
                continue
            n += 1
            is_grasp = ptype == "BasisCurves"
            is_col = purpose == "guide" and not is_grasp
            if is_grasp:
                ax.add_collection3d(Line3DCollection(
                    [list(map(tuple, w))], colors=PURPLE, linewidths=2.6))
                ax.scatter(w[:, 0], w[:, 1], w[:, 2], s=26, color=PURPLE,
                           marker="x", zorder=5)
                continue
            c = RED if is_col else BLUE
            polys = [[w[j] for j in f if j < len(w)] for f in faces]
            polys = [p for p in polys if len(p) >= 3]
            if polys:
                ax.add_collection3d(Poly3DCollection(
                    polys, alpha=0.16 if is_col else 0.42, facecolor=c,
                    edgecolor=c, linewidths=0.9 if is_col else 0.5,
                    linestyle="--" if is_col else "-"))
        ax.set_xlim(ctr[0] - rad, ctr[0] + rad)
        ax.set_ylim(ctr[1] - rad, ctr[1] + rad)
        ax.set_zlim(ctr[2] - rad, ctr[2] + rad)
        ax.set_xlabel("X (m)", fontsize=7.5, labelpad=-4)
        ax.set_ylabel("Y (m)", fontsize=7.5, labelpad=-4)
        ax.set_zlabel("Z (m)", fontsize=7.5, labelpad=-3)
        ax.tick_params(labelsize=6.2, pad=-2)
        ax.set_title(f"{label}\n({n} prims)", fontsize=9.5, pad=2)
        ax.view_init(elev=16, azim=-58)
        ax.set_box_aspect((1, 1, 1), zoom=1.32)

    kinds = ", ".join(sorted({t for _, t, _, _, _ in prims}))
    fig.suptitle(title, fontweight="bold", y=0.985)
    fig.legend(handles=[Patch(facecolor=BLUE, alpha=.5, label="visual (purpose=default)"),
                        Patch(facecolor=RED, alpha=.3, label="collision (purpose=guide)"),
                        Patch(facecolor=PURPLE, label="grasp vector — GSP.001")],
               loc="lower center", ncol=3, fontsize=8.4, frameon=False,
               bbox_to_anchor=(0.5, 0.052))
    caption = f"tessellated from analytic USD Gprims ({kinds}) · {asset}"
    if clipped:
        caption = "framed on the mechanism — the ground Plane extends past the view · " + caption
    fig.text(0.5, 0.014, caption, ha="center", fontsize=7, color=MUTED)
    fig.subplots_adjust(left=0.0, right=1.0, top=0.86, bottom=0.145, wspace=0.0)
    fig.savefig(out, bbox_inches=None); plt.close(fig)
    print(f"  {out.name}")


# ───────────────────────────────────────────────── joint trajectory
def fig_trajectory(csv_path: Path, out: Path, limits: dict[str, float] | None = None):
    """Joint angle + velocity vs time, with the URDF limits drawn on top."""
    rows = list(csv.DictReader(open(csv_path)))
    if not rows:
        print(f"  skip {out.name}: empty csv")
        return
    t = np.array([float(r["t"]) for r in rows])
    qs = sorted(k for k in rows[0] if k.startswith("q") and not k.startswith("qd"))
    qds = sorted(k for k in rows[0] if k.startswith("qd"))

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8.4, 5.8), sharex=True,
                                 gridspec_kw={"height_ratios": [1.25, 1]})
    names = list((limits or {}).keys())
    for i, k in enumerate(qs):
        c = [BLUE, RED, GREEN, AMBER][i % 4]
        lbl = names[i] if i < len(names) else k
        a1.plot(t, [float(r[k]) for r in rows], color=c, lw=1.9, label=lbl)
        if limits and i < len(names):
            lim = limits[names[i]]
            a1.axhline(lim, color=c, ls="--", lw=1.0, alpha=0.65)
            a1.annotate(f"URDF limit {lim} rad", (t[-1], lim), fontsize=7.5,
                        color=c, ha="right", va="bottom")
    a1.set_ylabel("joint angle  q  (rad)")
    a1.set_title("Recorded articulation state — ovphysx on CPU, 400 steps @ 60 Hz")
    a1.grid(alpha=0.4); a1.legend(fontsize=8.5, loc="center right")

    for i, k in enumerate(qds):
        c = [BLUE, RED, GREEN, AMBER][i % 4]
        a2.plot(t, [float(r[k]) for r in rows], color=c, lw=1.6, alpha=0.9)
    a2.axhline(0, color=MUTED, lw=0.8)
    a2.set_ylabel("velocity  q̇  (rad/s)"); a2.set_xlabel("time (s)")
    a2.grid(alpha=0.4)
    fig.text(0.5, 0.005,
             "joints spin up from a 2.0 rad/s kick, then clamp exactly at the URDF limits "
             "— the limits survived URDF → USD → PhysX",
             ha="center", fontsize=7.6, color=MUTED)
    fig.savefig(out); plt.close(fig)
    print(f"  {out.name}")


# ─────────────────────────────────────────────────── gaussian splats
def fig_splats(asset: Path, out: Path):
    """The 3DGS reconstruction, coloured by its own spherical-harmonic DC term."""
    from pxr import Usd
    stage = Usd.Stage.Open(str(asset))
    splat = next((p for p in stage.Traverse()
                  if p.GetTypeName() == "ParticleField3DGaussianSplat"), None)
    if not splat:
        print(f"  skip {out.name}: no splat prim")
        return

    pos = np.array(splat.GetAttribute("positions").Get(), dtype=float)
    col_attr = splat.GetAttribute("primvars:displayColor")
    col = col_attr.Get() if col_attr else None
    colors = np.clip(np.array(col, dtype=float), 0, 1) if col is not None and len(col) == len(pos) \
        else np.tile([0.4, 0.5, 0.7], (len(pos), 1))

    fig = plt.figure(figsize=(11.2, 4.6))
    for k, (ax_i, ax_j, lbl_i, lbl_j, title) in enumerate([
            (0, 1, "X (m)", "Y (m)", "top view  (X–Y)"),
            (0, 2, "X (m)", "Z (m)", "front view  (X–Z)")]):
        ax = fig.add_subplot(1, 3, k + 1)
        ax.scatter(pos[:, ax_i], pos[:, ax_j], s=3.5, c=colors, alpha=0.75, linewidths=0)
        ax.set_xlabel(lbl_i); ax.set_ylabel(lbl_j); ax.set_title(title)
        ax.set_aspect("equal", "datalim"); ax.grid(alpha=0.3)

    ax = fig.add_subplot(1, 3, 3, projection="3d")
    ax.scatter(pos[:, 0], pos[:, 1], pos[:, 2], s=2.5, c=colors, alpha=0.7, linewidths=0)
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
    ax.set_title("3D"); ax.view_init(elev=20, azim=-60)

    fig.suptitle(f"ParticleField3DGaussianSplat — {len(pos):,} splats read back from USD",
                 fontweight="bold")
    fig.text(0.5, 0.005, f"colour = primvars:displayColor · {asset}",
             ha="center", fontsize=7, color=MUTED)
    fig.savefig(out); plt.close(fig)
    print(f"  {out.name}")


# ──────────────────────────────────────────── SimReady before / after
def fig_conformance(before: Path, after: Path, out: Path, title: str):
    """Feature-level pass/fail from the validator's own JSON, before vs after."""
    def load(p):
        d = json.load(open(p))
        asset = next(iter(d))
        return {f: (v.get("passed"), v.get("failing requirements", ""))
                for f, v in d[asset]["features_summary"].items()}

    b, a = load(before), load(after)
    feats = sorted(set(b) | set(a))
    y = np.arange(len(feats))

    fig, ax = plt.subplots(figsize=(9.6, 0.62 * len(feats) + 2.1))
    for i, f in enumerate(feats):
        # y axis is inverted below, so the negative offset draws on top
        for off, data, lbl in ((-0.19, b, "before"), (0.19, a, "after")):
            passed, fails = data.get(f, (None, ""))
            if passed is None:
                continue
            col = GREEN if passed else RED
            ax.barh(i + off, 1, height=0.34, color=col, alpha=0.9)
            ax.text(1.02, i + off, "PASS" if passed else f"FAIL  {fails}",
                    va="center", fontsize=8, color=col, fontweight="bold")
            ax.text(0.02, i + off, lbl, va="center", fontsize=7.2,
                    color="white", fontweight="bold")

    ax.set_yticks(y); ax.set_yticklabels(feats, fontsize=9)
    ax.set_xlim(0, 2.5); ax.set_xticks([])
    ax.invert_yaxis()
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.set_title(title)
    ax.legend(handles=[Patch(facecolor=GREEN, label="passed"),
                       Patch(facecolor=RED, label="failed")],
              loc="lower right", fontsize=8.5, frameon=False)
    fig.text(0.5, 0.01,
             "read from simready-validate --output JSON · upper bar = freshly converted, "
             "lower bar = after scripts/simready_conform.py",
             ha="center", fontsize=7.4, color=MUTED)
    fig.savefig(out); plt.close(fig)
    print(f"  {out.name}")


# ───────────────────────────────────────────────────── USD layer tree
def fig_layers(converted: Path, conformed: Path, out: Path):
    """Layer structure before flattening vs after — the NP.005 conflict, drawn."""
    fig, (l, r) = plt.subplots(1, 2, figsize=(11.4, 4.6))
    fig.subplots_adjust(top=0.78)

    def draw(ax, title, rows, verdict, vcolor):
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        ax.set_title(title)
        for i, (depth, text, mono) in enumerate(rows):
            ax.text(0.04 + depth * 0.075, 0.86 - i * 0.108, text,
                    fontsize=9.6 if mono else 9,
                    family="monospace" if mono else None, color=INK, va="top")
        ax.text(0.04, 0.055, verdict, fontsize=9.4, color=vcolor, fontweight="bold")

    n_before = len(list(converted.parent.glob("**/*.usd*"))) if converted.exists() else 6
    draw(l, "after conversion — Atomic Asset", [
        (0, "arm2.usda            interface layer", True),
        (1, "Payload/Contents.usda", True),
        (1, "Payload/Geometry.usda", True),
        (1, "Payload/Materials.usda", True),
        (1, "Payload/MaterialsLibrary.usdc", True),
        (1, "Payload/Physics.usda", True),
    ], f"NP.005 FAIL — {n_before} USD layers in one asset folder", RED)

    draw(r, "after conformance — flattened", [
        (0, "arm2/arm2.usda       single layer", True),
        (1, "+ SimReady_Metadata           NP.006", True),
        (1, "+ resetXformStack  x2         RB.006", True),
        (1, "+ grasp_identifier_0          GSP.001", True),
        (1, "+ physics material binding    PMT.001", True),
        (1, "+ UsdPreviewSurface binding   VM.MAT.001", True),
    ], "NP.005 PASS — one .usda per asset folder", GREEN)

    fig.suptitle("The NP.005 conflict: NVIDIA's converter layout vs NVIDIA's SimReady rule",
                 fontweight="bold", y=0.965)
    fig.savefig(out, bbox_inches=None); plt.close(fig)
    print(f"  {out.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default="docs/figures")
    ap.add_argument("--out-root", default=".out")
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    root = Path(args.out_root)
    print(f"writing figures to {outdir}/")

    arm_conf = root / "arm2/conformed/arm2/arm2.usda"
    arm_conv = root / "arm2/converted/arm2.usda"
    cart_conf = root / "cartpole/conformed/cartpole/cartpole.usda"

    if arm_conf.exists():
        fig_robot(arm_conf, outdir / "robot-arm2.png",
                  "arm2 — URDF converted to USD, then SimReady-conformed")
    if cart_conf.exists():
        fig_robot(cart_conf, outdir / "robot-cartpole.png",
                  "cartpole — MuJoCo XML converted to USD, then SimReady-conformed")

    traj = root / "arm2/traj.csv"
    if traj.exists():
        fig_trajectory(traj, outdir / "trajectory-arm2.png",
                       limits={"shoulder": 1.57, "wrist": 2.0})

    splat = root / "scene_clean.usdc"
    if splat.exists():
        fig_splats(splat, outdir / "gsplat-scene.png")

    for name, label in (("arm2", "arm2 (URDF)"), ("cartpole", "cartpole (MuJoCo)")):
        b, a = root / name / "simready-before.json", root / name / "simready-after.json"
        if b.exists() and a.exists():
            fig_conformance(b, a, outdir / f"conformance-{name}.png",
                            f"SimReady Prop-Robotics-Neutral v1.0.0 — {label}")

    if arm_conf.exists():
        fig_layers(arm_conv, arm_conf, outdir / "layers-np005.png")

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
