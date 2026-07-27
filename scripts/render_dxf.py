#!/usr/bin/env python3
"""
render_dxf.py — draw a DXF to PNG so you can see what is in it.

Production drawings are often a whole *set* tiled into one modelspace: several
sheets, each with title block, BOM and multiple views. Numbers alone cannot tell
you that; a picture can. This renders the sheet, and optionally splits it into
regions by finding the empty gaps between them, so each can be looked at
individually.

Uses ezdxf's own drawing add-on, so blocks (INSERT) are expanded properly.

    python render_dxf.py part.dxf --out .out/look
    python render_dxf.py set.dxf  --out .out/look --split      # one PNG per region
    python render_dxf.py set.dxf  --out .out/look --window 3314 8561 6959 11642
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def anchors(msp):
    """One representative point per entity — enough to find the gaps between sheets."""
    pts = []
    for e in msp:
        try:
            t = e.dxftype()
            if t in ("INSERT", "TEXT", "MTEXT"):
                p = e.dxf.insert; pts.append((p.x, p.y))
            elif t == "LINE":
                pts.append(((e.dxf.start.x + e.dxf.end.x) / 2,
                            (e.dxf.start.y + e.dxf.end.y) / 2))
            elif t in ("CIRCLE", "ARC"):
                pts.append((e.dxf.center.x, e.dxf.center.y))
            elif t == "LWPOLYLINE":
                a = np.array([(x, y) for x, y, *_ in e.get_points()])
                pts.append(tuple(a.mean(axis=0)))
            elif t == "POLYLINE":
                a = np.array([[v.dxf.location.x, v.dxf.location.y] for v in e.vertices])
                if len(a):
                    pts.append(tuple(a.mean(axis=0)))
        except Exception:
            continue
    return np.asarray(pts, float)


def gaps(values, gap):
    """Split a 1-D spread wherever there is an empty run wider than `gap`."""
    s = np.sort(values)
    brk = np.where(np.diff(s) > gap)[0]
    edges = [s[0]] + [(s[i] + s[i + 1]) / 2 for i in brk] + [s[-1]]
    return edges


def render(doc, msp, out: Path, window=None, dpi=110, size=14.0, target_px=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    if window:
        x0, y0, x1, y1 = window
        ar = max((y1 - y0) / max(x1 - x0, 1e-9), 0.1)
        fig = plt.figure(figsize=(size, min(size * ar, 40)))
    else:
        fig = plt.figure(figsize=(size, size * 1.3))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
    if window:
        # the backend pins a data aspect of 1, so matplotlib will widen whichever
        # axis it must and ignore half of what we ask for — read back what it
        # actually used, or every crop derived from it lands in the wrong place
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    if target_px:
        # size the output by pixels, not by a dpi guessed from drawing units —
        # the backend may have changed the data limits under us
        dpi = max(30, int(target_px / max(fig.get_size_inches())))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="white")
    used = (ax.get_xlim(), ax.get_ylim())
    plt.close(fig)
    return out, used


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf")
    ap.add_argument("--out", default=".out/dxf-look", help="output directory")
    ap.add_argument("--split", action="store_true",
                    help="also render each detected region separately")
    ap.add_argument("--gap", type=float, default=400.0,
                    help="empty run that separates regions, in drawing units")
    ap.add_argument("--window", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"),
                    help="render only this box")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--target-px", type=int, default=5000,
                    help="long side of the full render in pixels; crops come from it")
    args = ap.parse_args()

    import ezdxf
    doc = ezdxf.readfile(args.dxf)
    msp = doc.modelspace()
    outdir = Path(args.out)

    if args.window:
        p, _ = render(doc, msp, outdir / "window.png", window=args.window, dpi=args.dpi)
        print(f"  {p}")
        return 0

    P = anchors(msp)
    if len(P) < 2:
        print("  nothing to render")
        return 0
    lo, hi = P.min(axis=0), P.max(axis=0)

    if not args.split:
        p, _ = render(doc, msp, outdir / "overview.png", dpi=args.dpi)
        print(f"  {p}")
        return 0

    # Render the sheet ONCE, then crop. Re-rendering per region means walking
    # every block reference again for each crop, which on a real drawing set is
    # minutes rather than seconds.
    pad = 0.01 * float((hi - lo).max())
    win = (lo[0] - pad, lo[1] - pad, hi[0] + pad, hi[1] + pad)
    full, used = render(doc, msp, outdir / "overview.png", window=win,
                        size=20.0, target_px=args.target_px)
    (ux0, ux1), (uy0, uy1) = used            # what matplotlib really drew
    uspan = (ux1 - ux0, uy1 - uy0)
    print(f"  {full}")

    from PIL import Image
    img = Image.open(full)
    W, H = img.size

    gx, gy = gaps(P[:, 0], args.gap), gaps(P[:, 1], args.gap)
    n = 0
    print(f"  regions (separated by gaps > {args.gap:g} drawing units):")
    for i in range(len(gy) - 1):
        for j in range(len(gx) - 1):
            sel = ((P[:, 0] >= gx[j]) & (P[:, 0] <= gx[j + 1]) &
                   (P[:, 1] >= gy[i]) & (P[:, 1] <= gy[i + 1]))
            if sel.sum() < 20:                     # ignore stray marks
                continue
            n += 1
            m = 0.02 * max(gx[j + 1] - gx[j], gy[i + 1] - gy[i])
            x0, y0 = gx[j] - m, gy[i] - m
            x1, y1 = gx[j + 1] + m, gy[i + 1] + m
            # drawing coords -> image pixels (y flips)
            px0 = int((x0 - ux0) / uspan[0] * W)
            px1 = int((x1 - ux0) / uspan[0] * W)
            py0 = int((uy1 - y1) / uspan[1] * H)
            py1 = int((uy1 - y0) / uspan[1] * H)
            crop = img.crop((max(px0, 0), max(py0, 0), min(px1, W), min(py1, H)))
            p = outdir / f"region-{n:02d}.png"
            crop.save(p)
            print(f"    {p.name}  x {x0:.0f}..{x1:.0f}  y {y0:.0f}..{y1:.0f}"
                  f"  ({sel.sum()} entities, {crop.size[0]}x{crop.size[1]} px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
