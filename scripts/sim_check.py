#!/usr/bin/env python3
"""
sim_check.py — prove a conformed asset still simulates.

Conformance edits change the stage: they reset transform stacks, bind physics
materials and flatten layers. Any of those can silently break dynamics, and a
validator PASS says nothing about that. This is the counter-check.

Runs on CPU. ovphysx falls back from GPU broadphase to ePABP automatically, so
no CUDA context is needed for rigid bodies. Deformables and particles are
skipped in that mode — see docs/02-verified-findings.md §5.

Usage:
    python sim_check.py conformed/arm2/arm2.usda [--steps 120] [--dt 0.0166667]
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asset", help="USD asset to simulate")
    ap.add_argument("--steps", type=int, default=120)
    ap.add_argument("--dt", type=float, default=1.0 / 60.0)
    args = ap.parse_args()

    import ovstage
    from ovphysx import PhysX

    if not ovstage.population.available():
        print("ERROR: ovstage population bridge unavailable", file=sys.stderr)
        return 2

    physx = PhysX()
    stage = ovstage.Stage("sim-check")
    try:
        ovstage.population.open_usd(
            stage, args.asset, ordinal=1,
            domains=ovstage.PopulationDomain.PHYSICS)
        physx.attach_ovstage(stage, read_ordinal=1)

        for _ in range(args.steps):
            physx.step_sync(args.dt)

        print("SIMULATED %d steps OK (dt=%.6f) on: %s"
              % (args.steps, args.dt, args.asset))
        return 0
    except Exception as exc:
        print("SIMULATION FAILED on %s: %s: %s"
              % (args.asset, type(exc).__name__, exc), file=sys.stderr)
        return 1
    finally:
        try:
            physx.detach_ovstage()
            stage.destroy()
        finally:
            physx.release()


if __name__ == "__main__":
    raise SystemExit(main())
