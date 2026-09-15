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

visualizer-build:
    cd skills/sssf/apps/visualizer && bun install --frozen-lockfile && bun run build

verify: fmt-check lint typecheck test plugin-check skill-check docs-check visualizer-build

copilot-smoke:
    uv run python scripts/copilot_smoke.py
