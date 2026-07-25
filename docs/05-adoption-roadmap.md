# 05 · Adoption roadmap

Your goal: **agent-driven development automation grounded in the Omniverse ecosystem**,
rather than a general coding assistant improvising against unfamiliar APIs.

The difference is not the model. It is that Omniverse gives you a **machine-checkable
definition of done**. `simready-validate` returns feature-level pass/fail with stable
requirement codes and exit status. An agent with that signal can iterate to a verified
result; an agent without it can only produce plausible-looking output.

So the ordering principle throughout: **install the checker before the generator.**

---

## Stage 0 — Ground truth (1 day, no GPU)

```bash
./scripts/bootstrap_env.sh
./scripts/run_pipeline.sh examples/urdf/arm2.urdf
```

You now have a working conversion → validation → conformance → simulation loop, and a
pipeline that exits non-zero on regression.

Then swap in one of your own assets. If it is URDF or MuJoCo the path is identical; if it
is CAD (STEP/JT/DGN) you need `usd-convert-cad`, which requires a Kit runtime and CAD
Converter licensing — plan for that separately.

**Exit criterion:** one of *your* assets reaches `[PASSED]` against a SimReady profile.

---

## Stage 1 — CI gate (2–3 days, no GPU)

Make conformance a merge requirement. `run_pipeline.sh` is already shaped for this.

```yaml
# .github/workflows/simready.yml
name: SimReady conformance
on: [pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y libopengl0 libglx0 libgl1
      - run: ./scripts/bootstrap_env.sh
      - run: ./scripts/run_pipeline.sh examples/urdf/arm2.urdf
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: reports, path: .out/**/*.json }
```

Two things that will save you time:

- **Cache `~/.cache/warp/`.** Warp JIT-compiles on first launch — 3.5 s measured, and it
  grows with kernel count.
- **Cache both venvs.** `bootstrap_env.sh` creates `.venv-ov` and `.venv-simready`
  separately because `usd-exchange` and `usd-core` cannot share a venv
  ([why](02-verified-findings.md#1-install-trap-usd-core-and-usd-exchange-cannot-coexist)).

**Exit criterion:** a PR that degrades asset conformance fails CI without human review.

---

## Stage 2 — Agent in the loop (1 week)

Now add the agent, pointed at the residual work the deterministic tools cannot do.

```bash
npx skills add nvidia/skills \
  --skill omniverse-cad-to-simready omniverse-usd-performance-tuning \
  --agent claude-code --yes
```

Give the agent this division of labour — it is the single highest-leverage decision here:

| Signal | Handler |
|---|---|
| `nvidia_usd_validate --fix` → `SUCCESS` | tool. Never invoke a model. |
| `FixStatus.NO_LOCATION` | agent — decide which layer should own the metadata |
| `FixStatus.NO_SUGGESTION` | agent — real data error, needs judgement |
| SimReady requirement failure | `simready_conform.py` if the code is handled; agent otherwise |
| unhandled requirement code | agent — **read `capabilities/**/validation.py`**, then extend the fixer |

That last row is the loop that compounds. The specification is executable Python, so an
agent that hits an unknown requirement can read the checker, implement the fix, and add
it to `simready_conform.py` — the fixer gets better and the *deterministic* share of the
work grows. Cross-check every such change with a re-validate run; a fix that passes the
checker but breaks simulation is a regression, which is why `run_pipeline.sh` ends with
a physics step.

**Exit criterion:** `simready_conform.py` handles every requirement code your assets hit,
and the agent is only invoked for genuinely novel ones.

---

## Stage 3 — GPU capabilities (2–4 weeks, needs hardware)

Only now does a GPU pay for itself. Prerequisites: Linux x86_64, Ampere+ with 16 GB+
VRAM (24–48 GB recommended for NuRec), Docker + NVIDIA Container Toolkit, an NGC API key,
and a Hugging Face token with the PhysicalAI gated licenses accepted.

Order by payoff:

1. **`ovrtx` rendering / sensor sim** — smallest step; unlocks synthetic data generation
   from assets you already conform.
2. **Isaac Sim / Isaac Lab** — RL at scale. `ovphysx` environment cloning already works on
   CPU (verified, 4 envs), so your scene-setup code carries over.
3. **NuRec Real2Sim** — highest setup cost. Do this only when you have capture data;
   otherwise use the PhysicalAI datasets on Hugging Face via `physical-ai-datasets`.
4. **Cosmos Transfer / OSMO workflows** — needs a cluster; sequence last.

Deploy the [MCP servers](04-mcp-setup.md) at this stage too, when you start writing Kit
extensions and Isaac Sim code rather than just processing assets.

---

## Stage 4 — Closed loop

Compose the stages into the shape `i4h-*` demonstrates
([`03-sim2real-real2sim.md §3`](03-sim2real-real2sim.md)):

```
scene edit → dataset generation → training → validation → deployment
     ▲                                                        │
     └──────── real-world failures become new scenarios ◄──────┘
```

Copy two of its design decisions specifically: make every stage separately invocable
*and* provide a single `-e2e` entry point; and treat `smoke` and `validate` as
first-class stages. Fast checks are what make an autonomous loop safe to leave running.

---

## What to build yourself

The catalog has real gaps. These are worth owning:

| Gap | Why it matters |
|---|---|
| **Requirement-code → fixer registry** | `simready_conform.py` covers 6 codes. There are dozens. A dispatch table keyed by code, with the agent authoring new entries, is the core asset. Adding `VM.MAT.001` cost one read of the checker and ~40 lines — that is the unit of work. |
| **Converter-output conformance profile** | NP.005 (one USD per folder) contradicts the Atomic Asset layout NVIDIA's own converters emit. Decide your house rule once — flatten, or use `.usdc` sublayers — and encode it. |
| **Physics-preserving regression tests** | Conformance edits can silently change dynamics. `sim_check.py` proves the asset still steps; a stronger version would compare trajectories before and after. |
| **Real2Sim post-process** | `gsplat_postprocess.py` is 40 lines and turns unusable reconstructions into valid assets. Run it on every NuRec output. |

---

## Cost and risk

| | |
|---|---|
| **Free, no GPU** | all conversion, validation, conformance, rigid-body physics, 3DGS→USD, the entire skill catalog |
| **Needs `NVIDIA_API_KEY`** | 4 MCP servers, Content Agents material/physics assignment |
| **Needs GPU** | rendering, sensor sim, deformables/particles, NuRec training, Isaac Lab |
| **Needs a cluster** | OSMO workflows (Cosmos Transfer, AnomalyGen, video augmentation) |

Three risks worth naming:

- **Skills execute with full agent permissions.** The `skills` CLI scans on install and
  says so. These carry `scripts/run.py` files. Review before running, pin versions, and
  verify signatures with `model_signing verify certificate` against
  `nv-agent-root-cert.pem`.
- **The ecosystem is days old.** Omniverse Libraries were announced 2026-07-20. Version
  churn is guaranteed — pin everything (`scripts/requirements-ov.txt` does).
- **Two NVIDIA tools already disagree** (NP.005 vs Atomic Asset). Expect more such seams,
  and keep your reconciliation in one place rather than scattered through scripts.
