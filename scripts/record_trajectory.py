#!/usr/bin/env python3
"""
record_trajectory.py — step a conformed asset and record joint state to CSV.

Where sim_check.py only answers "does it still simulate", this answers "what
does it do", which is what you actually need to see whether a conformance edit
changed dynamics. Emits one row per step.

Usage:
    python record_trajectory.py .out/arm2/conformed/arm2/arm2.usda \
        --pattern '/arm2/Geometry/base_link*' --steps 300 --csv .out/arm2/traj.csv
"""

from __future__ import annotations

import argparse
import csv
import sys

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asset")
    ap.add_argument("--pattern", required=True,
                    help="prim pattern for the articulation, e.g. '/arm2/Geometry/base_link*'")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--dt", type=float, default=1.0 / 60.0)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--kick", type=float, default=0.0,
                    help="initial DOF velocity (rad/s) applied to every dof. "
                         "A robot whose links are colinear with gravity sits in "
                         "unstable equilibrium and never moves without one.")
    args = ap.parse_args()

    import ovstage
    from ovphysx import PhysX, TensorType

    physx = PhysX()
    stage = ovstage.Stage("trajectory-recorder")
    dof_pos = dof_vel = None
    try:
        ovstage.population.open_usd(stage, args.asset, ordinal=1,
                                    domains=ovstage.PopulationDomain.PHYSICS)
        physx.attach_ovstage(stage, read_ordinal=1)
        physx.wait_all()

        dof_pos = physx.create_tensor_binding(
            pattern=args.pattern, tensor_type=TensorType.ARTICULATION_DOF_POSITION)
        dof_vel = physx.create_tensor_binding(
            pattern=args.pattern, tensor_type=TensorType.ARTICULATION_DOF_VELOCITY)

        if dof_pos.count == 0:
            print(f"ERROR: no articulation matched {args.pattern}", file=sys.stderr)
            return 2

        n_dof = dof_pos.shape[1]
        print(f"articulations={dof_pos.count}  dofs={n_dof}")

        pos = np.zeros(dof_pos.shape, dtype=np.float32)
        vel = np.zeros(dof_vel.shape, dtype=np.float32)

        if args.kick:
            vel[:] = args.kick
            dof_vel.write(vel)
            print(f"applied initial dof velocity {args.kick} rad/s")

        with open(args.csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["step", "t"]
                       + [f"q{i}" for i in range(n_dof)]
                       + [f"qd{i}" for i in range(n_dof)])
            for step in range(args.steps):
                physx.step_sync(args.dt)
                dof_pos.read(pos)
                dof_vel.read(vel)
                w.writerow([step, round(step * args.dt, 6)]
                           + [float(x) for x in pos[0]]
                           + [float(x) for x in vel[0]])

        print(f"wrote {args.csv}: {args.steps} steps x {n_dof} dofs")
        return 0
    finally:
        for b in (dof_pos, dof_vel):
            if b is not None:
                b.destroy()
        try:
            physx.detach_ovstage()
            stage.destroy()
        finally:
            physx.release()


if __name__ == "__main__":
    raise SystemExit(main())
