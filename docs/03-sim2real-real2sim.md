# 03 · Sim2Real and Real2Sim in the Omniverse ecosystem

Two directions, different tools, different bottlenecks.

- **Real2Sim** — the physical world becomes a simulatable asset.
- **Sim2Real** — a policy trained in simulation survives contact with reality.

USD is the interchange format in both directions; the SimReady profile is the contract
that says an asset is fit to simulate.

---

## 1. Real2Sim

```
  sensors                reconstruction              asset                simulation
┌──────────┐          ┌────────────────┐        ┌──────────────┐      ┌──────────────┐
│ video    │          │ ncore          │        │ usd-convert- │      │ Isaac Sim    │
│ LiDAR    │─────────►│  → NCore V4    │───────►│   gsplat     │─────►│ ovphysx      │
│ IMU      │  amc-*   │ nre            │  PLY   │  → USD       │ USD  │ CARLA        │
│ poses    │  calib   │  → 3DGS train  │        │ asset-       │      │ AlpaSim      │
└──────────┘          │ nurec-fixer    │        │  harvester   │      └──────────────┘
                      └────────────────┘        └──────────────┘
```

### Stages

| Stage | Tool | Skill | GPU |
|---|---|---|---|
| Camera extrinsics from video/RTSP | AutoMagicCalib | `amc-setup-calibration-stack`, `amc-run-video-calibration`, `amc-run-sample-calibration` | yes |
| Sensor recordings → NCore V4 | `nvidia-ncore` | `ncore` | yes |
| Train 3D Gaussian reconstruction | NRE (`nvcr.io/nvidia/nre/nre`) | `nre` | Ampere+, 16 GB+ |
| Extract per-object splat assets | Asset Harvester | `asset-harvester` | yes |
| Harmonize renders | DiffusionHarmonizer | `nurec-fixer` | yes |
| **3DGS → USD** | **`usd-convert-gsplat`** | — | **no** ✅ |
| Serve to a simulator | NuRec `serve-grpc` | `physical-ai-neural-reconstruction` | yes |

### What was verified

Only the conversion stage runs without a GPU — but it is the stage that decides whether
the reconstruction is usable downstream. See [`02-verified-findings.md §6`](02-verified-findings.md).

```
2000-splat PLY ──► ParticleField3DGaussianSplat prim
                   positions, opacities, orientations, scales,
                   radiance:sphericalHarmonicsCoefficients
```

**The default output fails NVIDIA's own validator** on two counts — USDZ byte alignment,
and a default prim that is neither Xformable nor Scope. Both are fixed by
[`scripts/gsplat_postprocess.py`](../scripts/gsplat_postprocess.py) (write `.usdc`,
wrap under a `/World` Xform), taking failures from 2 to 0.

Put that post-process immediately after reconstruction. A splat asset that cannot be
transformed is also one you cannot place, align or instance in a scene — the validator
failure and the practical problem are the same problem.

### Skipping reconstruction

If you do not have capture hardware, `physical-ai-datasets` catalogs NVIDIA's
**PhysicalAI** datasets on Hugging Face (gated — accept the licenses first). A published
alternative path exports Gaussian splats + a collider mesh from a generated world model,
converts the PLY through NuRec, and aligns it in Isaac Sim. Same USD landing point,
no capture rig.

---

## 2. Sim2Real

```
   asset prep              randomize             train              transfer            deploy
┌──────────────┐      ┌──────────────┐     ┌────────────┐     ┌────────────┐     ┌──────────┐
│ CAD/URDF     │      │ Isaac Lab DR │     │ Isaac Lab  │     │ Cosmos     │     │ Jetson   │
│  → SimReady  │─────►│ physics +    │────►│ RL / IL    │────►│  Transfer  │────►│ DeepStream│
│ ovphysx clone│      │ rendering    │     │ ovphysx    │     │ (photoreal)│     │ Holoscan │
└──────────────┘      └──────────────┘     └────────────┘     └────────────┘     └──────────┘
        ▲                                                                              │
        └──────────────────── real failures become new scenarios ◄─────────────────────┘
```

### The domain gap has two halves

**Visual gap** — synthetic frames do not look like camera frames.
Addressed by **Cosmos Transfer**: it takes synthetic multi-view video and produces
photorealistic output *while preserving scene structure*, so labels stay valid. The
Physical AI skills (`physical-ai-video-data-augmentation`,
`physical-ai-defect-image-generation`, `physical-ai-people-attribute-search`) are the
agent front-ends for these workflows on OSMO.

**Dynamics gap** — simulated contact, friction and mass do not match reality.
Addressed by **domain randomization** in Isaac Lab, which randomizes both physics and
rendering parameters so the policy cannot overfit one parameterization.

SimReady conformance is upstream of both. `PMT.001` — every collider carries a physics
material — exists because friction and restitution are exactly the parameters DR
randomizes. An asset with unbound physics materials has nothing to randomize, so its
policies overfit whatever default the engine picked.

### Where agents fit

| Task | Agent-suitable? | Why |
|---|---|---|
| Asset conversion + conformance | ✅ strongly | deterministic, machine-checkable, high volume |
| Choosing DR ranges | ⚠️ partly | agent can scaffold configs; the ranges are an engineering judgement |
| Launching / monitoring training | ✅ | `physical-ai-infrastructure-*`, OSMO skills |
| Diagnosing a policy that fails on hardware | ❌ | needs real-world observation |
| Turning a real failure into a new sim scenario | ✅ | scene edit + dataset generation are scripted |

---

## 3. The published closed loop: `i4h-*`

Isaac for Healthcare's 18 skills are the most complete example of an agent-run Sim2Real
loop in the catalog. Even outside medical robotics, the **stage decomposition** is the
part to copy:

```
i4h-workflow-setup      environment bring-up
i4h-workflow-create     new workflow scaffold
i4h-workflow-scene-edit modify the simulated scene
i4h-workflow-dataset-teleop     human demonstration capture
i4h-workflow-dataset-mimic      demonstration → many trajectories
i4h-workflow-dataset-annotate   labelling
i4h-workflow-dataset-convert    format conversion (LeRobot etc.)
i4h-workflow-dataset-replay     replay for verification
i4h-workflow-finetune           policy training
i4h-workflow-validate           validation
i4h-workflow-e2e                whole loop
i4h-lerobot-viz                 inspect trajectories
```

Plus a Real2Sim branch: `i4h-catheter-navigation-digital-twin`,
`-render-drr` (rendering real X-ray-like images from simulation), `-viewport`, `-smoke`.

Two design decisions worth stealing:

1. **Every stage is separately invocable, and there is a separate `-e2e` skill.**
   Debug one stage without rerunning the loop; run the loop without stitching stages.
2. **`-smoke` and `-validate` are first-class skills**, not afterthoughts. Fast checks
   are what make an autonomous loop safe to leave running.

---

## 4. Honest limits

| Claim | Status |
|---|---|
| 3DGS → USD works on CPU and the output can be made validator-clean | **verified here** |
| SimReady conformance is automatable end-to-end | **verified here** — 6 failures → PASS |
| Rigid-body physics runs on CPU for CI | **verified here** — 4/4 samples, 1000 steps |
| NuRec reconstruction quality | not tested — needs GPU + NGC + HF licenses |
| Cosmos Transfer closes the visual gap | vendor claim; not reproduced here |
| Isaac Lab DR improves real-world transfer | established in the literature; not reproduced here |

Treat rows 4–6 as design inputs to validate on your own hardware, not as results.
