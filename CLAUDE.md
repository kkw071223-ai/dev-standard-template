# CLAUDE.md — agent instructions for this repository

This repo is an **agent-driven Omniverse development environment**. Your job here is to
prepare, validate and conform 3D assets for physical-AI simulation, and to extend the
automation that does it.

Everything documented here was executed and verified. Do not replace verified commands
with plausible-looking alternatives.

---

## Read first

| When | Read |
|---|---|
| always | [`docs/02-verified-findings.md`](docs/02-verified-findings.md) — the traps are real and will cost you an hour each |
| catalog questions | [`docs/01-catalog.md`](docs/01-catalog.md) |
| Sim2Real / Real2Sim work | [`docs/03-sim2real-real2sim.md`](docs/03-sim2real-real2sim.md) |
| MCP / Kit / Isaac code | [`docs/04-mcp-setup.md`](docs/04-mcp-setup.md) |
| planning work | [`docs/05-adoption-roadmap.md`](docs/05-adoption-roadmap.md) |

---

## Environment — non-negotiable

Two venvs. They cannot be merged.

```bash
source .env.ov     # defines OV_VENV, SR_VENV, SIMREADY_FOUNDATION_SPEC_ROOT
```

| venv | contains | use for |
|---|---|---|
| `$OV_VENV` (`.venv-ov`) | `usd-exchange` (provides `pxr`), converters, `ovphysx`/`ovstage`/`ovrtx`, Newton/Warp | authoring, conversion, `nvidia_usd_validate`, physics |
| `$SR_VENV` (`.venv-simready`) | `simready-validate`, `usd-core`, asset validator | SimReady profile conformance |

**Never `pip install usd-core` into `$OV_VENV`.** `usd-exchange` vendors its own OpenUSD
under `pxrInternal_v0_25_5` and owns `site-packages/pxr`. Two copies of those symbols in
one process aborts the interpreter. `bootstrap_env.sh` fails loudly if it detects this.

If an import crashes with
`pxrInternal_v0_25_5__pxrReserved__::pxr_boost::python::error_already_set`
or `free(): invalid pointer`, that is this bug. Rebuild the venv; do not try to pin around it.

---

## Standard workflow

```bash
./scripts/bootstrap_env.sh                      # idempotent
./scripts/run_pipeline.sh examples/urdf/arm2.urdf
```

The pipeline is the contract: convert → USD-validate → SimReady baseline → conform →
SimReady re-validate → 120-step physics smoke. It exits non-zero if any stage regresses.
Reports land in `.out/<asset>/*.json`.

Both bundled fixtures reach `[PASSED] Prop-Robotics-Neutral v1.0.0`, 6/6 features.
**If either stops passing, you broke something** — that is the regression signal.

---

## Division of labour — read this before "fixing" anything

Most validation failures should never reach a model. Route by signal:

| Signal | Handler | Rule |
|---|---|---|
| `nvidia_usd_validate --fix` → `FixStatus.SUCCESS` | the tool | do not invoke reasoning |
| `FixStatus.NO_LOCATION` | you | decide which layer owns the metadata |
| `FixStatus.NO_SUGGESTION` | you | genuine data error, needs judgement |
| SimReady code already in `simready_conform.py` | the script | just run it |
| **SimReady code not yet handled** | you | see below — this is the real work |

### Handling an unknown requirement code

The specification is executable Python. Read it rather than guessing:

```bash
source .env.ov
grep -rn "CODE" $SIMREADY_FOUNDATION_SPEC_ROOT/capabilities/**/validation.py
```

Then: implement the fix in `scripts/simready_conform.py`, wire it into `main()`, and
re-run the pipeline on **both** fixtures. Each code you add moves work from the
non-deterministic column to the deterministic one permanently.

Worked example — `VM.MAT.001` appeared only on the MuJoCo path, because the MuJoCo
converter emits geometry without visual materials while the URDF converter emits them
from `<material>` tags. Reading
`capabilities/visualization/materials/validation.py::check_vm_mat_001_mesh_material_binding`
showed it wants a computed material on every GPrim whose purpose is `default` or
`render`. `bind_visual_materials()` was written from that, and both paths now pass.

### Non-negotiable check

A conformance edit that breaks dynamics is a regression, not a fix. `run_pipeline.sh`
ends with `sim_check.py` for this reason — never remove that stage, and never report a
conformance change as done without it passing.

---

## Currently handled requirement codes

| Code | Fix | Function |
|---|---|---|
| NP.005 | flatten to one `.usda` under `asset_folder/name/name.usda` | `main()` |
| NP.006 | `SimReady_Metadata` in root layer `customLayerData` | `stamp_metadata` |
| RB.006 | `SetResetXformStack(True)` on each nested dynamic rigid body | `fix_nested_rigid_bodies` |
| GSP.001 | `grasp_identifier_0` BasisCurves, ≥2 points, `purpose=guide` | `add_grasp_vector` |
| PMT.001 | bind `material:binding:physics` on every collider | `bind_physics_materials` |
| VM.MAT.001 | bind a `UsdPreviewSurface` on every renderable GPrim | `bind_visual_materials` |

Two subtleties worth preserving:

- **RB.006** — the validator clears a prim only when *that prim itself* carries the
  reset. An ancestor's reset does not cover descendants. Do not reintroduce the
  early-`break` walk-up; it silently leaves the deepest body failing.
- **GSP.001** — the grasp curve is authored with `purpose = guide` so it is exempt from
  `VM.MAT.001`. Changing its purpose creates a circular requirement.

---

## Conventions

- Verify claims by running commands; paste real output, never paraphrase it.
- Pin versions in `scripts/requirements-*.txt`. This ecosystem shipped in July 2026 and
  churns.
- Skills execute with full agent permissions. Review `scripts/run.py` before running an
  installed skill; verify signatures against `nv-agent-root-cert.pem` when it matters.
- Assume no GPU unless told otherwise. Rigid-body physics, all conversion and all
  validation run on CPU; rendering, deformables, particles and NuRec training do not.
- `.out/`, `.venv-*/` and `.env.ov` are generated — never commit them.
