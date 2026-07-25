# Omniverse Agent Stack

An agent-driven development environment built on the **NVIDIA Omniverse** ecosystem —
not on a general-purpose coding assistant alone.

Everything in this repository was **executed and verified in a sandbox** (Linux x86_64,
Python 3.11, **no GPU**). Commands, outputs, failures and fixes are recorded as observed,
not summarized from documentation.

---

## What this repository gives you

| | |
|---|---|
| **Catalog** | Every Omniverse-related agent, skill, MCP server and library, counted and named — [`docs/01-catalog.md`](docs/01-catalog.md) |
| **Evidence** | What actually ran, with real inputs/outputs and the traps that bite — [`docs/02-verified-findings.md`](docs/02-verified-findings.md) |
| **Sim2Real / Real2Sim** | How the pieces compose into closed loops — [`docs/03-sim2real-real2sim.md`](docs/03-sim2real-real2sim.md) |
| **MCP setup** | The 4 Omniverse MCP servers, ports, tools, client config — [`docs/04-mcp-setup.md`](docs/04-mcp-setup.md) |
| **Adoption** | A staged plan to get from zero to agent-run pipelines — [`docs/05-adoption-roadmap.md`](docs/05-adoption-roadmap.md) |
| **Working code** | A conformance agent that takes a converted robot from *failing* to *SimReady PASS* — [`scripts/`](scripts/) |

---

## The headline result

A robot asset was driven end-to-end through the real toolchain:

```
arm2.urdf                                    3 links, 2 revolute joints
   │
   ├─ urdf_usd_converter ─────────────────►  USD Atomic Asset (6 layers)
   │                                          nvidia_usd_validate: PASS
   │
   ├─ simready-validate ──────────────────►  FAIL — 6 issues, 2/6 features
   │                                          NP.005 NP.006 RB.006 GSP.001 PMT.001
   │
   ├─ scripts/simready_conform.py ────────►  flatten + 4 targeted fixes
   │
   ├─ simready-validate ──────────────────►  PASS — 6/6 features
   │
   └─ ovphysx ────────────────────────────►  120 simulation steps, stable
```

The same pipeline on a MuJoCo cartpole also reaches 6/6 — after adding one more fix
(`VM.MAT.001`), because the MuJoCo converter omits visual materials the URDF converter
emits. Different converters fail different requirements; test more than one.

The gap between "converted" and "simulation-ready" is a handful of **specific,
machine-readable requirement codes**. That gap is the work an agent can own — and every
code you teach the fixer moves permanently out of the model's column. See
[`docs/02-verified-findings.md`](docs/02-verified-findings.md) for the full transcript.

---

## Quick start

```bash
# 1. Build the verified CPU environment (~3 min, no GPU needed)
./scripts/bootstrap_env.sh

# 2. Run the whole pipeline on the bundled robot
./scripts/run_pipeline.sh examples/urdf/arm2.urdf

# 3. Install the Omniverse agent skills into this repo
npx skills add nvidia/skills \
  --skill omniverse-cad-to-simready omniverse-usd-performance-tuning \
  --agent claude-code --yes
```

`run_pipeline.sh` prints a stage-by-stage report and exits non-zero if any stage regresses,
so it works as a CI gate as-is.

---

## Scale of the ecosystem

| Layer | Count | Verified |
|---|---|---|
| Omniverse / Physical AI skills (top-level routers) | 8 | ✅ installed |
| ├─ nested sub-skills under those routers | 81 | ✅ enumerated |
| SimReady Foundation skills | 25 | ✅ cloned |
| Isaac-for-Healthcare (`i4h-*`) skills | 18 | ✅ enumerated |
| Camera-calibration (`amc-*`) skills | 3 | ✅ enumerated |
| Skills bundled inside `pip install ovphysx` | 6 | ✅ executed |
| Omniverse MCP servers | 4 (34 tools) | ⚠️ needs API key |
| `pip`-installable Omniverse libraries | 11 of 13 | ✅ installed |
| NVIDIA skills catalog (all products) | 322 dirs | ✅ cloned |

Your "40–50+" estimate was low for the Omniverse slice alone: **141 skill units** are
reachable before counting the wider NVIDIA catalog.

---

## What works without a GPU

This matters more than it sounds — it decides whether agents can run in CI.

| Capability | CPU | Notes |
|---|---|---|
| USD authoring / inspection (`usd-exchange`) | ✅ | full OpenUSD Python |
| URDF → USD, MuJoCo → USD | ✅ | seconds |
| 3DGS PLY → USD (`usd-convert-gsplat`) | ✅ | 2k splats < 1 s |
| `nvidia_usd_validate` (+ `--fix`) | ✅ | JSON out, exit 1 on fail |
| `simready-validate` profile conformance | ✅ | feature-level JSON |
| Rigid-body physics (`ovphysx`, Newton/Warp) | ✅ | auto-falls back to CPU |
| Deformables, particles, `EnvIds` filtering | ❌ | CUDA required |
| Rendering / sensor sim (`ovrtx`) | ❌ | RTX GPU required |
| NuRec 3DGS *training* | ❌ | Ampere+, 16 GB+ VRAM |

So: **the entire asset-preparation and validation half of the pipeline is CI-able on
CPU runners.** Only reconstruction, rendering and large-scale RL need GPUs.

---

## Layout

```
docs/         analysis and setup guides (5 documents)
scripts/      bootstrap, pipeline runner, conformance agent, Real2Sim post-process
examples/     the URDF / MuJoCo / 3DGS fixtures used in every verified run
.mcp.json     Omniverse MCP server registration
CLAUDE.md     session instructions for agents working in this repo
```

## Sources

- [NVIDIA/skills](https://github.com/NVIDIA/skills) · [NVIDIA-Omniverse/kit-usd-agents](https://github.com/NVIDIA-Omniverse/kit-usd-agents) · [NVIDIA/simready-foundation](https://github.com/NVIDIA/simready-foundation) · [NVIDIA/nurec-skills](https://github.com/NVIDIA/nurec-skills)
- [Omniverse Libraries](https://developer.nvidia.com/omniverse) · [Agent Toolkit + Omniverse Libraries announcement (2026-07-20)](https://nvidianews.nvidia.com/news/nvidia-agent-toolkit-expands-with-new-omniverse-libraries-putting-ai-agents-to-work-building-simulation-ready-worlds)
