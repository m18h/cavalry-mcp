# cavalry-mcp

A [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI assistants full, two-way control of [Cavalry](https://cavalry.studio) — the 2D motion design software — from natural language.

Create layers, set attributes, connect nodes, animate with keyframes and Magic Easing, render frames, and — uniquely — **see the results**, because this server gets *real return values* back from Cavalry.

```
MCP client (Claude Desktop, Claude Code, …)
    │  stdio (MCP)
    ▼
cavalry-mcp  (Python, FastMCP)
    │  HTTP 127.0.0.1:8722 — POST /post {id, code}, poll GET /get
    ▼
cavalry-mcp-bridge.js  (UI script running inside Cavalry)
    │  eval() → captures return value, console output, errors
    ▼
Cavalry  (tested against 2.7.2)
```

## Why not Stallion?

[Stallion](https://github.com/scenery-io/stallion) (and every existing Cavalry MCP built on it) is *fire-and-forget*: Cavalry's `api.WebServer` cannot return data in a POST response, so Stallion always replies `"Success"` — scripts can't return values and errors vanish into Cavalry's log window.

cavalry-mcp ships its own tiny bridge script that publishes each execution's result (value + console logs + error with stack) via `setResultForGet()`, which the Python side polls for. Same one-time install model as Stallion, but with a real request/response protocol.

## Requirements

- Cavalry 2.4+ (developed and tested on **2.7.2**), macOS or Windows
- Python 3.11+ (managed automatically by [uv](https://docs.astral.sh/uv/))

## Setup

### 1. Install the MCP server

```bash
git clone https://github.com/m18h/cavalry-mcp.git && cd cavalry-mcp
uv sync --extra kb
```

### 2. Install the bridge script into Cavalry

```bash
uv run cavalry-mcp install-bridge
```

This copies `cavalry-mcp-bridge.js` into Cavalry's Scripts folder
(`~/Library/Application Support/Cavalry/Scripts/` on macOS, `%APPDATA%\Cavalry\Scripts\` on Windows).

### 3. Start the bridge in Cavalry

Open Cavalry, then click **Scripts → cavalry-mcp-bridge.js**. A small window appears: "Listening on http://127.0.0.1:8722". **Keep it open** while using the MCP server.

### 4. Configure your MCP client

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cavalry": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/cavalry-mcp", "--extra", "kb", "cavalry-mcp"]
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add cavalry -- uv run --directory /absolute/path/to/cavalry-mcp --extra kb cavalry-mcp
```

**OpenCode** (`~/.config/opencode/opencode.jsonc`):

```jsonc
{
  "mcp": {
    "cavalry": {
      "type": "local",
      "command": ["uv", "run", "--directory", "/absolute/path/to/cavalry-mcp", "--extra", "kb", "cavalry-mcp"],
      "enabled": true
    }
  }
}
```

> The `--extra kb` flag keeps the knowledge-base dependencies installed (plain
> `uv run` re-syncs the environment and would prune them). Without it the
> server still works; `cavalry_search_knowledge` then reports how to enable the KB.

Bridge host/port can be overridden with `CAVALRY_BRIDGE_HOST` / `CAVALRY_BRIDGE_PORT` env vars (default `127.0.0.1:8722`).

## Tools (49)

| Group | Tools |
|---|---|
| **Meta** | `cavalry_status`, `cavalry_run_script` (arbitrary JS escape hatch with real return values) |
| **Scene/comps** | `cavalry_get_scene_info`, `cavalry_get_comp_info` (fps, frame range, resolution), `cavalry_new_scene`, `cavalry_open_scene`, `cavalry_save_scene`, `cavalry_save_scene_as`, `cavalry_create_comp`, `cavalry_set_active_comp` |
| **Layers** | `cavalry_create_layer`, `cavalry_delete_layer`, `cavalry_rename_layer`, `cavalry_duplicate_layer`, `cavalry_list_layers`, `cavalry_get_selection`, `cavalry_select_layers`, `cavalry_get_layer_info`, `cavalry_set_parent`, `cavalry_set_in_out_frames` |
| **Attributes** | `cavalry_get_attributes`, `cavalry_get_attribute`, `cavalry_set_attribute`, `cavalry_connect`, `cavalry_disconnect_input`, `cavalry_disconnect_outputs`, `cavalry_set_expression`, `cavalry_set_generator`, `cavalry_add_dynamic_attribute` |
| **Animation** | `cavalry_set_keyframe`, `cavalry_set_keyframes` (batch), `cavalry_magic_easing`, `cavalry_modify_keyframe`, `cavalry_delete_animation`, `cavalry_play`, `cavalry_stop`, `cavalry_set_frame`, `cavalry_get_frame` |
| **Render/assets** | `cavalry_render_frame_png` 📷, `cavalry_viewport_screenshot` 📷, `cavalry_list_render_queue`, `cavalry_add_render_queue_item`, `cavalry_start_render`, `cavalry_render_all_background`, `cavalry_cancel_render`, `cavalry_load_asset`, `cavalry_add_asset_to_comp` |
| **API reference** | `cavalry_search_api` — searches ~420 documented Cavalry API functions/classes bundled from [cavalry-types](https://github.com/scenery-io/cavalry-types) |
| **Knowledge base** | `cavalry_search_knowledge` — semantic search over the full official Cavalry documentation (2,687 passages from 518 pages) |

📷 = returns the image inline so the AI can *see* and iterate on the result.

## Knowledge base

`cavalry_search_knowledge` answers concepts/how-tos ("loop an animation", "stagger a duplicator", "export Lottie") with passages from the official docs, using local embeddings — **no external services**:

- **Store**: 2,687 heading-aware, code-fence-safe chunks scraped from the docs sitemap, embedded with `BAAI/bge-small-en-v1.5` via [fastembed](https://github.com/qdrant/fastembed) (ONNX runtime — no PyTorch), shipped as bundled data files.
- **Query time**: fastembed + brute-force cosine over the vector file (milliseconds at this scale — no vector DB server needed).
- The base install works without it: the tool reports how to enable the KB instead of failing.

(Re)build the store after a docs refresh:

```bash
uv sync --extra kb   # first time only: fastembed, markdownify, beautifulsoup4
uv run python scripts/build_knowledge_base.py
```

Note: the first build (and first query on a new machine) downloads the ~130 MB embedding model to the HF cache. Fetched HTML is cached in `.cache/` for fast re-runs.

## Cheat sheet (Cavalry 2.7.x, verified live)

- Layer ids look like `basicShape#1`, `textShape#1`, `compNode#1`.
- Common layer types: `basicShape`, `textShape`, `null`, `group`, `colorPlane`, `duplicator`, `subMesh`, `connectShape`, `linearGradient`, `javaScript`, `imageAsset`, `stagger`, `trail`, `noiseDeformer`.
- Common attribute paths: `position.x`, `position.y`, `rotation`, `scale.x`, `scale.y`, `opacity`, `material.materialColor` (fill color — accepts `"#ff8800"`), `stroke.width`, `fontSize`, `text`.
  Attribute paths differ between versions (older docs say `fill.color` — wrong on 2.7.x); use `cavalry_get_attributes` to discover them.
- Keyframes take a dictionary: `api.keyframe(layerId, frame, {"position.x": 200})`.
- Magic Easing names: `SlowIn`, `SlowOut`, `SlowInSlowOut`, `VerySlow*`, `Spring*`, `SmallSpring*`, `AnticipateIn`, `OvershootOut`, `BounceIn`, `BounceOut`, `BounceInBounceOut`, `Custom` (with expression), `None`.

## Example conversation

> **You:** Create orange text saying "Hello Cavalry!" that bounces in from above, then show me frame 20.
>
> The assistant will: `cavalry_create_layer("textShape")` → set `text`, `fontSize`, `material.materialColor` → `cavalry_set_keyframes` on `position.y` → `cavalry_magic_easing("BounceOut")` → `cavalry_set_frame(20)` → `cavalry_render_frame_png` and show you the image.

## Development

```bash
uv sync                      # install deps (add --extra kb for knowledge base)
uv run pytest                # unit tests (mocked bridge, mocked KB)
uv run ruff check src tests scripts
uv run python scripts/build_api_reference.py   # rebuild the bundled API reference
uv run python scripts/build_knowledge_base.py  # rebuild the docs knowledge base
```

Project layout:

```
src/cavalry_mcp/
  server.py                  # FastMCP app + entry point
  bridge.py                  # async HTTP client (POST /post + poll /get, id-matched)
  install.py                 # bridge installer
  js/cavalry-mcp-bridge.js   # the in-Cavalry script (the protocol's other half)
  tools/                     # tool modules (meta, scene, layers, attrs, anim, render, apiref, knowledge)
  data/api_reference.json    # bundled from cavalry-types (see scripts/)
  data/knowledge_chunks.json # docs passages for the knowledge base (see scripts/)
  data/knowledge_vectors.npz # their embeddings (bge-small-en-v1.5)
scripts/build_api_reference.py
scripts/build_knowledge_base.py
vendor/cavalry-types/        # upstream .d.ts files the reference is built from
tests/
```

Live integration testing: open Cavalry with the bridge running, then call any tool — see `tests/` for the mocked suite that runs everywhere.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Cannot reach the cavalry-mcp bridge" | Open Cavalry → Scripts → cavalry-mcp-bridge.js, keep the window open. |
| Timed out waiting for a result | The bridge window was closed, or Cavalry is busy (e.g. mid-render). Retry. |
| Something else uses port 8722 | Set `CAVALRY_BRIDGE_PORT` on the Python side **and** edit `PORT` at the top of the bridge script. |
| Attribute set silently does nothing | The attribute path is wrong for this layer type/version — call `cavalry_get_attributes` and pick from the list. |
| Bridge misbehaving | Set `DEBUG = true` near the top of the bridge script and inspect `/tmp/cavalry-mcp-bridge-debug.log`. |

## Credits

- [Cavalry](https://cavalry.studio) by Scene Group
- [scenery-io/cavalry-types](https://github.com/scenery-io/cavalry-types) — machine-readable API definitions that power `cavalry_search_api`
- [scenery-io/stallion](https://github.com/scenery-io/stallion) — pioneered the in-Cavalry HTTP bridge concept
- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## License

MIT
