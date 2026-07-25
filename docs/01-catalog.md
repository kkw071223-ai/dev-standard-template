# 01 · Catalog — every Omniverse agent, skill, MCP server and library

Enumerated from official sources on 2026-07-25 by cloning the repositories and
listing their contents, not by reading marketing pages.

Provenance for each count is a shell command you can re-run; they are in
[`02-verified-findings.md`](02-verified-findings.md).

---

## 1. Skills — `github.com/NVIDIA/skills`

The catalog repository holds **322 skill directories** covering 50+ NVIDIA products.
Skills are portable directories containing a `SKILL.md` with YAML frontmatter
(`name`, `description`, `tools`, `compatibility`, `metadata`), plus optional
`references/`, `scripts/` and `shared/` subtrees.

Installed with the vendor-neutral `skills` CLI:

```bash
npx skills add nvidia/skills --skill <name> --agent claude-code --yes
```

Supported harnesses: **Claude Code, Codex, Cursor, Snowflake CoCo, Kiro CLI**.
Each skill ships `skill.oms.sig` (detached signature) and `skill-card.md` (governance
metadata); verify against `nv-agent-root-cert.pem` with `model_signing verify certificate`.

### 1.1 Omniverse skills (3 routers → 81 nested references)

These are **orchestrator/router** skills: the top-level `SKILL.md` routes to nested
`references/<name>/README.md` units, each with its own `scripts/run.py` and
`scripts/check_dependencies.py`.

| Router skill | Nested refs | Runnable scripts | Purpose |
|---|---:|---:|---|
| `omniverse-cad-to-simready` | 15 | 23 | CAD/URDF/MuJoCo → SimReady USD: convert, assign materials + physics, conform, validate, package |
| `omniverse-usd-performance-tuning` | 12 | 0 | Profile and optimize slow/heavy USD scenes; Scene Optimizer operations, before/after comparison |
| `omniverse-realtime-viewer` | 54 | 0 | Build a USD viewer: local/streaming/Tauri/Electron/C++, picking, gizmos, AOVs, overlays |

**`omniverse-cad-to-simready` nested references (15):**
`preflight` · `identify-asset-context` · `convert-to-usd` · `validate-usd-minimum` ·
`content-agents` · `deploy-content-agents` · `simready-conform-profile` ·
`simready-validate` · `omni-asset-validate` · `omni-asset-validate-geometry` ·
`omni-asset-validate-physics` · `assemble-package-source` · `nv-core-package-sample` ·
`nv-core-package-sample-validation` · `ovrtx-render-service`

**`omniverse-usd-performance-tuning` nested references (12):**
`setup-usd-performance-tuning` · `omniverse-authentication` · `profile-stage` ·
`usd-structure-assessment` · `usd-validation-runner` · `operations` · `so-run-operations` ·
`cad-conversion` · `compare-profiles` · `optimization-report` · `report-templates` · `upstreams`

**`omniverse-realtime-viewer`** covers 54 references across streaming
(`streaming-server`, `streaming-client`, `streaming-lifecycle`, `webgl-shm-transport`),
native shells (`tauri-local-viewer`, `electron-shm-viewer`, `cpp-native-viewer`),
interaction (`transform-manipulator`, `native-picking-selection`, `prim-pick-effects`)
and stage access (`stage-queries`, `stage-hierarchy`, `stage-attribute-reads`).

### 1.2 Physical AI skills (5)

| Skill | What it orchestrates | Backend |
|---|---|---|
| `physical-ai-neural-reconstruction` | Router for NuRec/NRE: USDZ rendering, NCore conversion, 3DGS, gRPC sensor sim | Docker + GPU + NGC + HF token |
| `physical-ai-defect-image-generation` | Cosmos AnomalyGen defect synthesis for PCBA / metal / glass AOI | OSMO |
| `physical-ai-video-data-augmentation` | Video augmentation + auto-labeling | OSMO |
| `physical-ai-people-attribute-search` | Person augmentation + re-ID auto-labeling | OSMO |
| `physical-ai-infrastructure-setup-and-resilient-scaling` | MicroK8s / Azure AKS / NVCF / NIM Operator / OSMO deployment | Kubernetes |

`physical-ai-neural-reconstruction` is a thin router; its real content lives upstream in
[`NVIDIA/nurec-skills`](https://github.com/NVIDIA/nurec-skills) as 6 sibling skills:
`nurec-index` · `physical-ai-datasets` · `ncore` · `nre` · `asset-harvester` · `nurec-fixer`.

### 1.3 SimReady Foundation skills (25)

Shipped inside [`NVIDIA/simready-foundation`](https://github.com/NVIDIA/simready-foundation)
under `skills/`. Two families:

**Conformance (11)** — make an asset satisfy one feature:
`conform-fet-000-core` · `conform-fet-001-minimal` · `conform-fet-003-rigid-body-physics` ·
`conform-fet-004-simulate-multi-body-physics` · `conform-fet-005-simulate-grasp-physics` ·
`conform-fet-006-materials` · `conform-fet-007-nonvisual-materials` ·
`conform-fet-021-robot-core` · `conform-fet-023-robot-materials` ·
`conform-fet-024-base-articulation` · `create-package`

**Spec authoring (14)** — extend the standard itself:
`add-`/`update-` × (`capability`, `feature`, `feature-adapter`, `profile`, `requirement`,
`validator`) plus `add-runtime-test` and `validate-foundation-change`.

### 1.4 Isaac-for-Healthcare `i4h-*` (18) and calibration `amc-*` (3)

`i4h-*` is the most complete *published* example of an agent-run Sim2Real loop —
scene edit → teleop → dataset → mimic → finetune → validate → digital twin. Even for
non-medical work it is the reference blueprint (see [`03-sim2real-real2sim.md`](03-sim2real-real2sim.md)).

`amc-*` (AutoMagicCalib) does multi-camera extrinsic calibration from video/RTSP —
the Real2Sim entry point for fixed-camera environments.

### 1.5 Bundled in the Python wheels (6)

`pip install ovphysx` also installs `SKILLS.md`, `skills/` (6), `samples/` (7 scripts)
and `docs/` (136 files) **inside site-packages**. Resolve with:

```python
import ovphysx; ovphysx.ai_skills_path()
# → {'skills_index': .../SKILLS.md, 'skills_dir': ..., 'samples_dir': ..., 'docs_dir': ...}
```

Skills: `basic-workflow` · `ovphysx-usd-authoring` · `ovphysx-output-read` ·
`clone-environments` · `tensor-bindings-cpu` · `tensor-bindings-gpu`.

This is a distribution pattern worth copying: **ship the agent playbook with the library**,
so the docs can never drift from the installed version.

---

## 2. MCP servers — `NVIDIA-Omniverse/kit-usd-agents`

Four servers, **34 tools total**, built on NeMo Agent Toolkit (NAT) 1.3+.
Each is a Docker container speaking streamable HTTP MCP. All require `NVIDIA_API_KEY`
from [build.nvidia.com](https://build.nvidia.com/settings/api-keys) for embeddings,
reranking and LLM access.

| Server | Port | Tools | Covers |
|---|---:|---:|---|
| `omni-ui-mcp` | 9901 | 10 | `omni.ui` widgets, styling, window layouts |
| `kit-mcp` | 9902 | 12 | 400+ Kit extensions, 1000+ settings, app templates |
| `usd-code-mcp` | 9903 | 7 | USD Atlas API DB, code examples, knowledge base |
| `isaacsim-mcp` | 9904 | 5 | Isaac Sim extensions, APIs, settings, best practices |

Full tool lists and client configuration: [`04-mcp-setup.md`](04-mcp-setup.md).

---

## 3. Omniverse Libraries (Python)

Announced 2026-07-20 as the "Omniverse Libraries" for the NVIDIA Agent Toolkit.
Install status verified by `pip install` in a clean venv:

| Package | PyPI | Version installed | Role |
|---|---|---|---|
| `usd-exchange` | ✅ | 2.3.0 | OpenUSD Exchange SDK — **also provides `pxr`** |
| `ovstage` | ✅ | 0.1.0.346039 | High-performance scene data layer |
| `ovphysx` | ✅ | 0.5.9 | USD-native PhysX; ships 6 agent skills |
| `ovrtx` | ✅ | 0.4.0.346409 | RTX rendering + sensor simulation (needs GPU) |
| `ovstream` | ✅ | 0.4.5 | GStreamer pixel streaming + remote input (**GPU-only**) |
| `ovstorage` | ✅ | 0.1.0 | Cloud-native asset APIs |
| `newton` | ✅ | 1.4.0 | Physics engine on Warp |
| `warp-lang` | ✅ | 1.15.0 | GPU kernel framework (**CPU fallback works**) |
| `usd-validation-nvidia` | ✅ | 1.20.0 | `nvidia_usd_validate` CLI |
| `urdf-usd-converter` | ✅ | 0.3.0 | URDF → USD |
| `mujoco-usd-converter` | ✅ | 0.4.0 | MuJoCo → USD |
| `simready-validate` | ✅ | 2026.4.9 | SimReady profile conformance |
| `usd-convert-gsplat` | ✅ | 0.1.15 | 3DGS PLY/SPZ → USD |
| `ovui` | ❌ | — | not on PyPI; source only |
| `usd-optimize` | ❌ | — | not on PyPI; source only |
| `usd-convert-asset` | ❌ | — | not on PyPI (the skill docs say so explicitly) |
| `usd-convert-cad` | ❌ | — | needs Kit runtime + CAD Converter licensing |
| `nurec` | ❌ | — | NGC containers only |

> **Install trap.** `usd-exchange` vendors its own complete OpenUSD build under the
> `pxrInternal_v0_25_5` namespace. Installing `usd-core` alongside it causes a hard
> crash. See [`02-verified-findings.md §1`](02-verified-findings.md).

---

## 4. The SimReady specification

`simready-foundation` defines a four-layer standard. Understanding it is what makes
agent-driven asset prep tractable — every failure is a stable, quotable code.

```
Profile      Prop-Robotics-Neutral, Prop-Robotics-Physx, Prop-Robotics-Isaac,
             Robot-Body-Neutral, Robot-Body-Runnable, Robot-Body-Isaac,
             Package, Package-NoBOM, Package-Candidate
   └─ Feature      52 spec files — FET000_CORE, FET001_BASE_NEUTRAL,
                   FET003_*_RIGID_BODY_PHYSICS, FET004_*_MULTI_BODY,
                   FET005_GRASP_PHYSICS, FET006_BASE_MDL, FET021_ROBOT_CORE,
                   FET100_BASE_ISAACSIM, ...
      └─ Capability    12 groups — core, physics_bodies, visualization,
                       hierarchy, semantic_labels, nonvisual_sensors,
                       packaging, isaac_sim, example
         └─ Requirement    atomic checks — NP.005, NP.006, RB.006,
                           GSP.001, PMT.001, UN.001, VG.MESH.001, ...
```

Variants matter: `_BASE_NEUTRAL` is engine-agnostic, `_BASE_PHYSX` adds PhysX-specific
collision approximation, `_BASE_ISAACSIM` adds Isaac composition. Pick the profile that
matches your runtime, not the strictest one.

---

## 5. Totals

| Layer | Units |
|---|---:|
| Omniverse router skills | 3 |
| └ nested references | 81 |
| Physical AI skills | 5 |
| └ NuRec upstream siblings | 6 |
| SimReady Foundation skills | 25 |
| `i4h-*` skills | 18 |
| `amc-*` skills | 3 |
| `ovphysx` bundled skills | 6 |
| **Omniverse-relevant skill units** | **147** |
| MCP tools | 34 |
| pip-installable libraries | 13 |
| NVIDIA/skills catalog (all products) | 322 |
