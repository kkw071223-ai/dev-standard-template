# 02 · Verified findings — what actually ran

Sandbox: Linux x86_64 (kernel 6.18.5), Python 3.11.15, 15 GB RAM, Docker 29.3.1,
Node 22.22.2, **no NVIDIA GPU** (`nvidia-smi: command not found`).

Every block below is real terminal output. Where something failed, the failure is kept
and the fix is shown after it.

---

## 1. Install trap: `usd-core` and `usd-exchange` cannot coexist

**Severity: blocking.** This is the first thing that will break for anyone following
the obvious `pip install usd-core usd-exchange`.

### Symptom

```
$ pip install usd-core usd-exchange urdf-usd-converter
$ urdf_usd_converter in/arm2.urdf out/arm2
terminate called after throwing an instance of
'pxrInternal_v0_25_5__pxrReserved__::pxr_boost::python::error_already_set'
```

Pinning `usd-core==25.5` to match the ABI namespace does *not* help — it changes the
crash to `free(): invalid pointer`.

### Root cause

Both wheels vendor a **complete, separate** copy of OpenUSD, and both use the same
C++ namespace `pxrInternal_v0_25_5`:

```
site-packages/usd_core.libs/       35 libs   libusd_usd-643bd47c.so   → pxrInternal_v0_25_5
site-packages/usd_exchange.libs/   29 libs   libusd_usd-aa06ec35.so   → pxrInternal_v0_25_5
```

Two copies of the same symbols load into one process; TfType registration runs twice and
the registry corrupts. Worse, `site-packages/pxr` is **owned by `usd-exchange`** — so
installing `usd-core` overwrites those files, and uninstalling it deletes them, leaving a
half-broken tree.

### Fix

Do not install `usd-core` at all. `usd-exchange` provides `pxr`.

```bash
python3 -m venv ovenv
./ovenv/bin/pip install usd-exchange urdf-usd-converter mujoco-usd-converter \
                        usd-validation-nvidia usd-convert-gsplat \
                        ovstage ovphysx ovrtx ovstream ovstorage newton
```

```
pxr           : OK
usdex.core    : OK, version = 2.3.0
UsdPhysics    : OK
```

### Cross-check

NVIDIA documents this, but only inside the wheel — `site-packages/ovphysx/SKILLS.md`:

> "ovphysx bundles its own OpenUSD libraries. It is not needed to install `usd-core`
> as a separate dependency -- doing so may cause version conflicts."

The `simready-validate` skill README also warns about the mirror-image problem on
aarch64, where `usd-core` has no wheel at all and `usd-exchange` is the required fallback.

**Corollary:** tools that *do* depend on `usd-core` — `simready-validate` pulls
`usd-core 26.8`, `omniverse-asset-validator`, `omniverse-usd-profiles` — must live in a
**separate venv**. The NVIDIA skills already do this, defaulting to
`$XDG_CACHE_HOME/physical-ai-skill-hub/simready-validate-venv`. Two venvs is the
architecture, not a workaround.

---

## 2. URDF → USD

### Input

`examples/urdf/arm2.urdf` — 1608 bytes, 3 links (box base, cylinder link, sphere
gripper), 2 revolute joints, full inertial + collision geometry.

### Command and output

```
$ urdf_usd_converter in/arm2.urdf out/arm2      # exit 0, < 2 s

out/arm2/arm2.usda                  ← interface layer
out/arm2/Payload/Contents.usda
out/arm2/Payload/Geometry.usda
out/arm2/Payload/Materials.usda
out/arm2/Payload/MaterialsLibrary.usdc
out/arm2/Payload/Physics.usda       ← 40 KB total
```

This is the **OpenUSD Exchange "Atomic Asset"** layering — a thin interface layer with a
`payload` arc to content layers, so consumers can load metadata without pulling geometry.

### What the converter decided for you

```usda
def Xform "arm2" (
    prepend apiSchemas = ["GeomModelAPI"]
    kind = "component"
    prepend payload = @./Payload/Contents.usda@
)
{ float3[] extentsHint = [(-0.1, -0.1, -0.125), (0.1, 0.1, 0.365), ...] }
```

```usda
def PhysicsRevoluteJoint "shoulder" ( prepend apiSchemas = ["NewtonJointAPI"] )
{
    float newton:velocityLimit = 114.59156
    uniform token physics:axis = "Y"
    rel physics:body0 = </arm2/Geometry/base_link>
    rel physics:body1 = </arm2/Geometry/base_link/link1>
    float physics:lowerLimit = -89.95438
    float physics:upperLimit = 89.95438
    custom float urdf:limit:effort = 50
}
```

Four things worth knowing:

1. **Radians → degrees.** URDF `lower="-1.57"` becomes `-89.95438`. Any code comparing
   limits across the boundary must convert, and 1.57 ≠ π/2 exactly — the rounding is
   inherited, not introduced.
2. **`NewtonJointAPI` is applied automatically**, and `newton:velocityLimit` is emitted
   in deg/s (2.0 rad/s → 114.59). You get Newton-engine coupling whether or not you
   asked for it.
3. **Engineering intent is preserved** as `custom float urdf:limit:effort` — the value
   has no USD physics meaning but survives the round trip. This is what "preserve
   engineering content" means in the CAD-to-SimReady announcement.
4. **A `PhysicsFixedJoint "root_joint"` is synthesized** binding `</arm2>` to the base
   link. Nothing in the URDF asked for it.

### MuJoCo → USD

`mujoco_usd_converter in/pend.xml out/cartpole` — same Atomic Asset shape (4 layers,
no separate MaterialsLibrary), exit 0, and it passes `nvidia_usd_validate` clean.

---

## 3. `nvidia_usd_validate` — the agent-facing validator

### On the converted robot

```
$ nvidia_usd_validate out/arm2/arm2.usda
INFO: No issues found.          # exit 0
```

### On a deliberately broken asset

```
$ nvidia_usd_validate in/broken.usda --json-output v.json      # exit 1
ERROR: [ExtentsChecker] Prim does not have any extent value At Prim </World/badmesh>
ERROR: [ExtentsChecker] Prim does not have any extent value At Prim </World/noextent>
ERROR: [StageMetadataChecker] Stage does not specify an upAxis.
ERROR: [SubdivisionSchemeChecker] Subdivision scheme is not set. ...
ERROR: [ValidateTopologyChecker] Invalid topology found At Prim </World/badmesh>
Failures: 6
```

**Exit code is 1 on failure, 0 on pass** — safe to use directly as a CI gate.

### Why the JSON matters for agents

```json
{
  "status": "FAIL",
  "rules": [{
    "rule": {"name": "SubdivisionSchemeChecker"},
    "issues": [{
      "message": "Subdivision scheme is not set. There are no normals on the mesh...",
      "severity": "FAILURE",
      "at": {"path": "/World/badmesh", "schema_class": "Mesh"},
      "suggestion": {"message": "Set subdivision scheme to Catmull-Clark"},
      "requirement": {"code": "com.nvidia.usd.VG.010", "version": "1.0.0"}
    }]
  }]
}
```

Every issue carries a **prim path**, a **stable requirement code** and a
**machine-readable suggestion**. An agent does not have to parse prose or guess where to
edit — this is a structured work queue.

### `--fix` auto-repair, and where it stops

```
$ nvidia_usd_validate in/tofix.usda --fix
Subdivision scheme is not set ......... FixStatus.SUCCESS      (×2)
Prim does not have any extent value ... FixStatus.SUCCESS      (×2)
Stage does not specify an upAxis ...... FixStatus.NO_LOCATION
Invalid topology found ................ FixStatus.NO_SUGGESTION

# re-validate → Failures: 2
```

4 of 6 repaired mechanically. The two that remain are exactly the ones needing judgement:
`NO_LOCATION` (no editable layer holds the stage metadata) and `NO_SUGGESTION` (the mesh
references vertex index 99 with only 4 points — a real data error).

**This is the division of labour.** Deterministic fixes belong to `--fix`; an agent should
only be invoked for `NO_LOCATION` and `NO_SUGGESTION`. Running an LLM over the other four
wastes tokens and adds risk.

---

## 4. SimReady conformance — the real gap

### The setup that works

`simready-validate` needs three spec paths. Omitting `--rules-path` silently degrades to
"every feature skipped, profile not found" — a misleading failure mode:

```
ERROR: Skipping feature 'FET001_BASE_NEUTRAL' because it contains unregistered
       requirements: ['AA.001', 'AA.002', 'UN.001', ...]
WARNING: Profile Prop-Robotics-Neutral not found.
```

Correct invocation (`$SF` = `simready-foundation/nv_core/sr_specs/docs`):

```bash
simready-validate <asset.usda> \
  --profile Prop-Robotics-Neutral --version 1.0.0 \
  --rules-path    $SF/capabilities \
  --features-path $SF/features \
  --profiles-path $SF/profiles/profiles.toml \
  --output result.json
```

### Result on the freshly converted robot

The asset that `nvidia_usd_validate` called clean fails SimReady on **six issues**:

| # | Requirement | Rule | Message |
|---|---|---|---|
| 0 | NP.005 | `AssetFolderStructureChecker` | No other USD files should exist in 'arm2' or its subfolders. Found: `Geometry.usda, Physics.usda, Materials.usda, Contents.usda` |
| 1 | RB.006 | `RigidBodyChecker` | Enabled rigid body missing xformstack reset, child of rigid body — at `/arm2/Geometry/base_link/link1` |
| 2 | RB.006 | `RigidBodyChecker` | same — at `.../link1/gripper` |
| 3 | GSP.001 | `GraspableVectorLineChecker` | Asset must have at least one grasp vector prim |
| 4 | NP.006 | `MetadataLocationChecker` | Asset has no metadata — needs `SimReady_Metadata` or sidecar JSON |
| 5 | PMT.001 | `PhysicsMaterialsCapabilityChecker` | Prim has a collision API but no `material:binding:physics` |

```json
"FET000_CORE":         {"passed": false, "failing requirements": "['NP.005', 'NP.006']"},
"FET001_BASE_NEUTRAL": {"passed": true},
"FET003_BASE_NEUTRAL": {"passed": false, "failing requirements": "['RB.006']"},
"FET004_BASE_NEUTRAL": {"passed": false, "failing requirements": "['RB.006']"},
"FET005_BASE_NEUTRAL": {"passed": false, "failing requirements": "['GSP.001', 'PMT.001']"},
"FET006_BASE_MDL":     {"passed": true}
```

**2 of 6 features pass.** Note issue #0: NVIDIA's own converter produces a layout that
NVIDIA's own SimReady rule rejects. NP.005 demands one USD file per asset folder; the
Atomic Asset pattern is multi-layer by design. These are two correct standards with
incompatible assumptions, and **something has to reconcile them** — that something is
the agent.

> `.usdc` files are not counted by NP.005 — only `.usd` and `.usda`. Flattening to a
> single `.usda` is the cleaner resolution and is what `simready_conform.py` does.

### Closing the gap

[`scripts/simready_conform.py`](../scripts/simready_conform.py) applies five targeted edits:

```json
{
  "RB.006_resetXformStack": ["/arm2/Geometry/base_link/link1",
                             "/arm2/Geometry/base_link/link1/gripper"],
  "GSP.001_grasp_vector":   "/arm2/grasp_identifier_0",
  "PMT.001_physics_material": {
      "material": "/arm2/PhysicsMaterials/DefaultPhysicsMaterial",
      "bound_prims": ["/arm2/Geometry/base_link/link1/gripper/sphere_1",
                      "/arm2/Geometry/base_link/link1/cylinder_1",
                      "/arm2/Geometry/base_link/box_1"]},
  "NP.006_metadata": {"asset_name": "arm2", "profile": "Prop-Robotics-Neutral", ...},
  "NP.005_flattened_to": "conformed/arm2/arm2.usda"
}
```

```
Asset: conformed/arm2/arm2.usda
  [PASSED] Prop-Robotics-Neutral v1.0.0        # exit 0

FET000_CORE  FET001_BASE_NEUTRAL  FET003_BASE_NEUTRAL
FET004_BASE_NEUTRAL  FET005_BASE_NEUTRAL  FET006_BASE_MDL     → all passed=True
```

### The bug worth keeping

First iteration left RB.006 failing. The fixer walked up the ancestor chain and stopped
at the first ancestor already carrying a reset — so `gripper` never got its own. Reading
`capabilities/physics_bodies/utils.py::_has_dynamic_body_parent` settles it:

```python
# early exit on immediate xformstack reset
if xform and xform.GetResetXformStack():
    return False, None
```

The validator only clears a prim when **that prim itself** carries the reset; an
ancestor's reset does not cover descendants. Removing the early `break` fixed it.

Two lessons. First, physically: URDF's kinematic tree becomes *nested* USD rigid bodies,
and nested dynamic bodies without a transform-stack reset produce undefined simulation —
this is a genuine correctness bug in naive conversion, not a paperwork rule. Second,
methodologically: **the specification is the source code.** `capabilities/**/validation.py`
is readable Python, so an agent stuck on a requirement should read the checker rather
than guess. That is a far better loop than trial-and-error against an opaque tool.

### Different converters fail different requirements

Running the same pipeline on the MuJoCo cartpole surfaced a requirement the URDF robot
never hit. The cause is a structural difference in how the two converters represent a
link, confirmed by listing every GPrim with its purpose and collider status:

| | arm2 (URDF) | cartpole (MuJoCo) |
|---|---|---|
| visual geometry | `purpose=default`, no `CollisionAPI` | **one prim does both** — `purpose=default` *and* `CollisionAPI` |
| collision geometry | separate prims, `purpose=guide` | (same prims as above) |
| in scope for VM.MAT.001 | visual only — materials came from `<material>` tags → pass | the dual-purpose prims, which have no material → **fail** |

The URDF converter separates the two representations and marks the collision copy
`purpose=guide`, which exempts it from VM.MAT.001. The MuJoCo converter reuses one prim
for both, so that prim is in scope for the material check. Neither is wrong — it is a
difference in convention, and it is invisible until you run both.

| | URDF `arm2` | MuJoCo `cartpole` |
|---|---|---|
| NP.005, NP.006 | fail | fail |
| RB.006 | fail (×2) | fail |
| GSP.001 | fail | fail |
| PMT.001 | fail | *pass* |
| **VM.MAT.001** | *pass* | **fail** |

`VM.MAT.001` requires a computed material binding on every GPrim whose purpose is
`default` or `render`. The URDF converter emits visual materials from `<material>` tags;
the MuJoCo converter emits geometry without them.

The fix followed straight from reading
`capabilities/visualization/materials/validation.py::check_vm_mat_001_mesh_material_binding` —
bind a `UsdPreviewSurface` to every unbound renderable GPrim (`bind_visual_materials`).
After that, **both** fixtures reach 6/6.

Two things this demonstrates. The obvious one: **test more than one source format**, since
each converter has its own blind spots. The more useful one: the loop compounds. A new
requirement code cost one read of the checker and ~40 lines, and that code is now
handled deterministically forever. That is the mechanism by which the agent's share of
the work shrinks over time.

One dependency worth noting: the GSP.001 grasp curve is authored with `purpose = guide`
specifically so VM.MAT.001 exempts it. Give it a renderable purpose and the two
requirements chase each other.

### Conformance did not break physics

Passing a validator is worthless if the asset stops simulating. Verified separately:

```
$ python sim_check.py conformed/arm2/arm2.usda
SIMULATED 120 steps OK on: conformed/arm2/arm2.usda
```

---

## 5. `ovphysx` — physics without a GPU

All four official samples in `site-packages/ovphysx/samples/python_samples/` run on CPU.

```
$ python hello_world.py
Using ovphysx version:  0.5.9
[Warning] GPU broadphase requires a CUDA context manager; falling back to ePABP.
Loaded scene through ovstage
Simulation step completed successfully
```

```
$ python clone.py                       # RL environment replication
Cloning /World/envs/env0 to 3 targets...
  Created 3 clones successfully
  Rigid body binding: count=4, shape=(4, 7)     # 4 bodies × [pos(3) + quat(4)]
  env0: pos=(-0.0006, 0.2424, -0.0012)
  env1: pos=(0.0005, 0.6521, -0.0023)
  env2: pos=(0.0014, 1.0352, 0.0038)
  env3: pos=(-0.0012, 1.4708, -0.0002)
```

```
$ python output_read.py                 # closed-loop read/write through ovstage
  frame 1: velocity x changed 2.000 -> -2.000 for 11 body(s); mean dx=-0.033333
  frame 1: dumped 4 output column group(s) to ovstage
Closed-loop ovstage output read completed successfully
```

`tensor_bindings.py` completes 1000 steps.

### The precise CPU/GPU boundary

| | CPU | Message when GPU is absent |
|---|---|---|
| Rigid bodies | ✅ | `GPU broadphase ... falling back to ePABP` |
| Environment cloning | ✅ | works, but `EnvIds requested but gpu dynamic is disabled` |
| Tensor bindings (DLPack) | ✅ | numpy on CPU; torch/CUDA on GPU |
| Deformables | ❌ | `deformable read needs a CUDA context — none available` |
| Particles | ❌ | `particle read needs a CUDA context — none available` |

So rigid-body regression tests are CI-able on plain runners. Soft-body and particle work
is not.

### `ovstream` is the one library with no CPU path

The developer page summarizes `ovstream` as "high-throughput GPU data sharing", which
reads like a storage or IPC layer. The installed package is something else: a
**GStreamer-based pixel-streaming and remote-input library** — the transport that carries
a rendered viewport to a client and carries mouse/keyboard/gamepad/touch back.

```
$ python -c "import ovstream; print(ovstream.__doc__)"
OVSTREAM SDK Python bindings.
    ovstream.initialize()
    with ovstream.Server(ovstream.ServerType.RTSP) as server:
        server.start(ovstream.ServerConfig(width=1920, height=1080))

ServerType     : WEBRTC, NATIVE, RTSP, SHM, CUDASHM
ClientType     : SHM, CUDASHM, NATIVE
InputEventType : KEYBOARD, MOUSE, GAMEPAD, TOUCH
frame types    : VideoFrame, AudioFrame, CudaSync
ServerConfig   : width, height, target_fps, stream_port, webrtc_signal_port,
                 webrtc_public_ip, rtsp_mount_point, rtsp_pipeline,
                 shm_stream_name, shm_slot_count, cudashm_*, cuda_context, cuda_device
```

The wheel ships `libgstrtspserver`, `libgstvideo`, `libgstapp` and `libcudart.so.12`, plus
a second package `ovstream_utils` (`Loop`, `LoopConfig`, `Stats`, `Tick`) for driving a
frame loop.

```
$ python -c "import ovstream; ovstream.initialize()"
OSError: libcuda.so.1: cannot open shared object file: No such file or directory
```

**It imports on CPU but cannot initialize.** That makes it the only Omniverse library
tested here with no CPU fallback — `ovphysx` degrades to `ePABP` broadphase, `warp` runs
its CPU backend, but `ovstream` needs NVENC and stops at `initialize()`.

Its place in the stack is a trio: `ovrtx` renders → `ovstream` transports → `ovui` puts an
interface on it. That is the subject of `omniverse-realtime-viewer` (54 nested references).
Irrelevant to asset preparation; relevant the moment you want a browser-served viewer.

### One missing system library

```
[Error] [carb] Could not load .../libcarb.usdresolver.plugin.so
        Error: libOpenGL.so.0: cannot open shared object file
[Warning] omniverse:// (Nucleus) URLs will not resolve. Local USD files are unaffected.
```

`apt-get install -y libopengl0 libglx0 libgl1` clears it and Nucleus URL resolution comes
back — on a headless machine with no GPU. Worth doing in any container image.

### Warp CPU backend

```
$ python warp_cpu_test.py
devices: ['cpu']
Module __main__ load on device 'cpu' took 3498.54 ms  (compiled)
after 100 steps (1.0s) ballistic on CPU:
  pos = [0.99999934 0. 5.0459476]   vel = [1. 0. -9.81]
```

Correct semi-implicit Euler. Note the **3.5 s JIT compile** on first launch — cache
`~/.cache/warp/` between CI runs or every job pays it.

Warp kernels must live in a real file; `python -c` fails with
`Directly evaluating Warp code defined as a string using exec() is not supported`.

---

## 6. Real2Sim: 3D Gaussian Splats → USD

Input: a synthetic 2000-splat reconstruction with the standard 3DGS property set
(`x y z`, `f_dc_0..2`, `opacity`, `scale_0..2`, `rot_0..3`) — the shape NuRec/NRE emits.

```
$ usd-convert-gsplat -i in/scene_recon.ply -o out/scene_recon.usdz --up-axis Z
[3DGS] Loaded 2,000 splats | SH degree: 0 coeffs
[3DGS] Saved -> out/scene_recon.usdz            # 112 KB PLY → 307 KB USDZ, exit 0
```

### The USD representation

```
/scene_recon    type = ParticleField3DGaussianSplat
   attrs: positions, opacities, orientations, scales, extent,
          radiance:sphericalHarmonicsCoefficients, radiance:sphericalHarmonicsDegree,
          primvars:displayColor
```

A first-class typed prim, not a point cloud hack — reconstructions compose into a USD
stage alongside CAD assets.

### But the default output fails validation

```
$ nvidia_usd_validate out/scene_recon.usdz
ERROR: [ByteAlignmentChecker] File 'default.usda' in package has an invalid offset 42.
ERROR: [DefaultPrimChecker] The default prim <scene_recon> of type
       "ParticleField3DGaussianSplat" is not Xformable nor a Scope type.
Failures: 2
```

### Fix — verified

| Failure | Fix | Result |
|---|---|---|
| `ByteAlignmentChecker` | write `.usdc`, not `.usdz` (USDZ needs 64-byte alignment) | 2 → 1 failures |
| `DefaultPrimChecker` | reference the splat under a `/World` `Xform` and make that the default prim | 1 → **0 failures** |

[`scripts/gsplat_postprocess.py`](../scripts/gsplat_postprocess.py) does both.
A reconstruction that fails validation will not survive an asset pipeline, so this
post-process belongs in every Real2Sim run.

---

## 7. Skill installation

```
$ npx skills add nvidia/skills --skill omniverse-cad-to-simready \
    omniverse-usd-performance-tuning physical-ai-neural-reconstruction \
    --agent claude-code --yes

  physical-ai-neural-reconstruction   Safe   0 alerts   Med Risk
  ✓ omniverse-cad-to-simready (copied)          → ./.claude/skills/...
  ✓ omniverse-usd-performance-tuning (copied)   → ./.claude/skills/...
  ✓ physical-ai-neural-reconstruction (copied)  → ./.claude/skills/...
Done!  Review skills before use; they run with full agent permissions.
```

A security scan runs before install. The warning is real — these skills carry
`scripts/run.py` files that execute with full agent permissions.

### The dependency-check contract

Every nested reference exposes `scripts/check_dependencies.py`, which is the cleanest
part of the whole design:

```
$ python references/simready-validate/scripts/check_dependencies.py --report dep.json
{
  "skill": "simready-validate",
  "passed": false,
  "checks": [
    {"name": "python_available", "passed": true, ...},
    {"name": "simready-validate_available_or_installable", "passed": false,
     "message": "not found; no Foundation requirements.txt found. Provide
                 simready-foundation checked out to main, or set SIMREADY_FOUNDATION_ROOT."}
  ],
  "errors": [...]
}
```

Structured, and the error message **names the remediation**. Following it verbatim
(clone `simready-foundation` to `~/.physical-ai-skill-hub/upstreams/`) took one step and
produced a working validator. Copy this pattern for your own skills.

---

## 8. What could not be verified here, and why

Stated plainly so nothing above is over-read:

| Area | Blocker |
|---|---|
| 4 Omniverse MCP servers | need `NVIDIA_API_KEY`; containers are GPU-optional but the cloud endpoints are not free |
| `ovrtx` rendering / sensor sim | requires an RTX GPU |
| NuRec / NRE 3DGS **training** | Ampere+, 16 GB+ VRAM, NGC key, HF gated licenses |
| Cosmos Transfer / AnomalyGen | OSMO cluster |
| `usd-convert-cad` (JT/DGN/HOOPS) | Kit runtime + CAD Converter licensing |
| Content Agents material/physics assignment | Docker + GPU + `NVIDIA_API_KEY` |
| Isaac Sim / Isaac Lab | GPU |

The library and skill *inventory* for these was confirmed from official repos; their
*runtime behaviour* was not. `ovrtx` imports cleanly on CPU (0.4.0), which only proves
the package installs.
