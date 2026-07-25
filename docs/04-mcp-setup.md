# 04 · Omniverse MCP servers

Four MCP servers from [`NVIDIA-Omniverse/kit-usd-agents`](https://github.com/NVIDIA-Omniverse/kit-usd-agents),
**34 tools total**, built on NeMo Agent Toolkit (NAT) 1.3+.

They are **knowledge servers, not actuators.** None of them opens a stage or edits a
file — they answer "what is the API / extension / setting / example for X" against
indexed NVIDIA documentation. The acting is done by the skills and the Python libraries.
That split is the right mental model: MCP for *knowing*, skills + libraries for *doing*.

> Not executed in this sandbox — they need an `NVIDIA_API_KEY` for embeddings, reranking
> and LLM access. Tool inventory below is read from the repository's own READMEs.

---

## Servers

| Server | Port | Tools | Image |
|---|---:|---:|---|
| `omni-ui-mcp` | 9901 | 10 | `omni-ui-mcp:ngc` |
| `kit-mcp` | 9902 | 12 | `kit-mcp:ngc` |
| `usd-code-mcp` | 9903 | 7 | `usd-code-mcp:ngc` |
| `isaacsim-mcp` | 9904 | 5 | `isaacsim-mcp:ngc` |

### `usd-code-mcp` — OpenUSD API (9903)

| Tool | Purpose |
|---|---|
| `list_usd_modules` | all USD module names |
| `list_usd_classes` | USD class names, filterable by module |
| `get_usd_module_detail` | detail for one module |
| `get_usd_class_detail` | full class detail |
| `get_usd_method_detail` | method signatures + docs |
| `search_usd_code_examples` | semantic search over USD examples |
| `search_usd_knowledge` | conceptual knowledge base |

### `kit-mcp` — Kit SDK (9902)

`get_kit_instructions` · `search_kit_app_templates` · `get_kit_app_template_details` ·
`search_kit_extensions` · `get_kit_extension_details` · `get_kit_extension_dependencies` ·
`get_kit_extension_apis` · `get_kit_api_details` · `search_kit_code_examples` ·
`search_kit_test_examples` · `search_kit_settings`

Covers 400+ extensions and 1000+ config settings — the part of Kit that is effectively
un-greppable by hand.

### `omni-ui-mcp` — `omni.ui` (9901)

`get_ui_instructions` · `get_ui_class_instructions` · `get_ui_style_docs` ·
`list_ui_modules` · `list_ui_classes` · `get_ui_module_detail` · `get_ui_class_detail` ·
`get_ui_method_detail` · `search_ui_code_examples` · `search_ui_window_examples`

### `isaacsim-mcp` — Isaac Sim (9904)

`get_isaac_sim_instructions` · `search_isaac_sim_extensions` ·
`get_isaac_sim_extension_details` · `search_isaac_sim_code_examples` ·
`search_isaac_sim_settings`

---

## Deploy

```bash
git clone https://github.com/NVIDIA-Omniverse/kit-usd-agents.git
cd kit-usd-agents/source/mcp

export NVIDIA_API_KEY=nvapi-...          # build.nvidia.com/settings/api-keys
./build-wheels.sh all
docker compose -f docker-compose.ngc.yaml up --build
```

Bring up only what you need — each service is independent:

```bash
docker compose -f docker-compose.ngc.yaml up usd-code-mcp kit-mcp
```

Health check:

```bash
curl -fL http://localhost:9903/mcp -X POST \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

---

## Client configuration

This repo ships [`.mcp.json`](../.mcp.json) with all four registered. It is inert until
the containers are running.

### Claude Code

```bash
claude mcp add usd-code-mcp  --scope user -t http http://localhost:9903/mcp
claude mcp add kit-mcp       --scope user -t http http://localhost:9902/mcp
claude mcp add omni-ui-mcp   --scope user -t http http://localhost:9901/mcp
claude mcp add isaacsim-mcp  --scope user -t http http://localhost:9904/mcp
```

> **Scoping.** Without `--scope user`, `claude mcp add -t http` writes `.claude.json` in
> the **current working directory**, and the server is only visible when you launch from
> there. This bites people; NVIDIA calls it out in their own README.

### Cursor

`.cursor/mcp.json` (or `~/.cursor/mcp.json` for global), then
`Cmd/Ctrl+Shift+P` → *Developer: Reload Window*:

```json
{ "mcpServers": { "usd-code-mcp": { "url": "http://localhost:9903/mcp" } } }
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `307 Temporary Redirect` on `POST /mcp/` | NAT 1.25 canonicalizes to `/mcp`; bare `curl -f` treats 307 as success so the healthcheck never runs | drop the trailing slash, or use `curl -fL` |
| `401 Unauthorized` | invalid/expired `NVIDIA_API_KEY` | regenerate at build.nvidia.com, update `.env` |
| `--env-file: file not found` | wrong cwd | run from `source/mcp/<server>/`, or `--env-file "$(git rev-parse --show-toplevel)/source/mcp/.env"` |
| server missing from `claude mcp list` | registered at project scope | re-add with `--scope user` |
| `connection refused` | container stopped | `docker ps`, restart the compose service |

---

## Is it worth it?

**Yes, if** you write Kit extensions, `omni.ui` panels, or Isaac Sim code. The extension
and settings catalogs are large enough that an unaided model will confidently invent
plausible-but-wrong names, and these servers are the corrective.

**Not yet, if** your work is asset preparation and validation — the pipeline in
[`scripts/`](../scripts/) does that with no API key, no GPU and no containers. Start
there; add MCP when you move into Kit/Isaac application code.
