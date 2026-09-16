set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

fmt:
    uv run ruff format .

fmt-check:
    uv run ruff format --check .

lint:
    uv run ruff check .

typecheck:
    uv run pyright

test:
    uv run pytest -q

plugin-check:
    uv run check-jsonschema --schemafile https://agent-plugins.org/schemas/1.0.0/plugin.schema.json plugin.json

skill-check:
    uv run pytest -q tests/test_plugin_layout.py -k canonical_skill

# Validate every Markdown link, including ai_docs.
docs-check:
    @command -v lychee >/dev/null || { echo "install lychee: brew install lychee or cargo install lychee"; exit 1; }
    @mkdir -p .cache
    @lychee --config lychee.toml '**/*.md'

# Are the tools SSSF needs on PATH? Prints each version; Bun is optional.
doctor:
    @ok=0; for tool in python3 uv git sqlite3 just copilot; do \
      if command -v "$tool" >/dev/null 2>&1; then printf '%-8s %s\n' "$tool" "$("$tool" --version 2>&1 | head -1)"; \
      else printf '%-8s MISSING\n' "$tool"; ok=1; fi; done; \
      if command -v bun >/dev/null 2>&1; then printf '%-8s %s (optional, visualizer only)\n' bun "$(bun --version)"; \
      else printf '%-8s missing (optional, visualizer only)\n' bun; fi; \
      exit $ok

# SDK/runtime preflight: CLI version, pinned SDK version, managed runtime download.
copilot-doctor:
    copilot --version
    uv run --with github-copilot-sdk==1.0.13 python -c "import importlib.metadata as m; print(m.version('github-copilot-sdk'))"
    uv run --with github-copilot-sdk==1.0.13 python -m copilot download-runtime

visualizer-build:
    cd skills/sssf/apps/visualizer && bun install --frozen-lockfile && bun run build

# One-time dependency install for the visualizer.
visualizer-install:
    cd skills/sssf/apps/visualizer && bun install --frozen-lockfile

# Read-only API server over a target repo's trace db (port 4600, override with PORT).
visualizer-server db="adws/adw_data/sssf.db":
    cd skills/sssf/apps/visualizer && bun run server/index.ts --db "{{absolute_path(db)}}"

# Vite dev UI on port 4601; proxies /api to the server started by visualizer-server.
visualizer-dev:
    cd skills/sssf/apps/visualizer && bun run dev

# Single-process mode: build the UI once, then serve API and UI together on port 4600.
visualizer db="adws/adw_data/sssf.db": visualizer-build
    cd skills/sssf/apps/visualizer && bun run server/index.ts --db "{{absolute_path(db)}}"

verify: fmt-check lint typecheck test plugin-check skill-check docs-check visualizer-build

copilot-smoke:
    uv run python scripts/copilot_smoke.py
