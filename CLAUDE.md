# Claude Notes for Gondola

## CRITICAL

- **THE CLI (venice/cli.py) IS VESTIGIAL AND UNUSED**
- **ONLY THE WEB UI (venice-web-ui/server.py) IS USED**
- **NEVER WASTE TIME MODIFYING THE CLI**

## Architecture

- Web UI backend: `venice-web-ui/server.py`
- Frontend: `venice-web-ui/static/` (script.js, style.css)
- Tools: `venice/tools/` (image_ops.py, etc.)
- API helpers: `venice/api.py`
- System prompts: `venice/prompts/system.py`

## Image Handling

- Avatar lives at: `gondola_v2.3/images/avatar.png`
- Expressions saved to: `gondola_v2.3/expressions/`
- Edit models: qwen-edit (fast), seedream-v4-edit (slow/better)
- When tool returns `image_base64`, server.py adds it as user message for vision model
