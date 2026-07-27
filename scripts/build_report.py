#!/usr/bin/env python3
"""
build_report.py — assemble the standalone HTML report.

Reads a page body from docs/*.body.html and inlines everything it references, so
the output is fully self-contained (no external requests, which an Artifact CSP
would block anyway).

Placeholders in the body:
    {{FIG:robot-arm2}}   -> data URI for docs/figures/robot-arm2.webp
    {{CSS:base}}         -> contents of docs/base.css, so pages share one system

Usage:
    python build_report.py --body docs/report.body.html --out docs/report.html
    python build_report.py --body docs/reference.body.html --out docs/reference.html
"""

from __future__ import annotations

import argparse
import base64
import re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", default="docs/report.body.html")
    ap.add_argument("--figures", default="docs/figures")
    ap.add_argument("--out", default="docs/report.html")
    args = ap.parse_args()

    body_path = Path(args.body)
    body = body_path.read_text(encoding="utf-8")
    figdir = Path(args.figures)

    # {{CSS:name}} -> docs/name.css, so every page shares one design system
    def css(m):
        p = body_path.parent / f"{m.group(1)}.css"
        if not p.exists():
            raise SystemExit(f"ERROR: missing stylesheet {p}")
        return p.read_text(encoding="utf-8")

    body = re.sub(r"\{\{CSS:([a-zA-Z0-9_-]+)\}\}", css, body)

    uris = {}
    for p in sorted(figdir.glob("*.webp")):
        uris[p.stem] = "data:image/webp;base64," + \
            base64.b64encode(p.read_bytes()).decode("ascii")

    missing = []

    def sub(m):
        name = m.group(1)
        if name not in uris:
            missing.append(name)
            return ""
        return uris[name]

    out = re.sub(r"\{\{FIG:([a-zA-Z0-9_-]+)\}\}", sub, body)

    if missing:
        print("ERROR: no figure for: " + ", ".join(sorted(set(missing))))
        print("available: " + ", ".join(sorted(uris)))
        return 1

    used = {m for m in re.findall(r"\{\{FIG:([a-zA-Z0-9_-]+)\}\}", body)}
    unused = sorted(set(uris) - used)

    dst = Path(args.out)
    dst.write_text(out, encoding="utf-8")
    kb = dst.stat().st_size / 1024
    print(f"wrote {dst}  ({kb:.0f} KB, {len(used)} figures inlined)")
    if unused:
        print("  note: figures not referenced by the body: " + ", ".join(unused))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
