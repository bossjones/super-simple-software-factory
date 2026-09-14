set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Validate every Markdown link, including ai_docs.
docs-check:
    @command -v lychee >/dev/null || { echo "install lychee: brew install lychee or cargo install lychee"; exit 1; }
    @mkdir -p .cache
    @GITHUB_TOKEN="$${GITHUB_TOKEN:-$$(gh auth token 2>/dev/null || true)}" \
      lychee --config lychee.toml '**/*.md'
