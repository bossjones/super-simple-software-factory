import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n")
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


def test_plugin_manifest_uses_agent_plugins_1():
    manifest = json.loads((ROOT / "plugin.json").read_text())
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "sssf"
    assert manifest["version"] == "1.0.0"
    assert manifest["description"] == (
        "Install and operate deterministic agents-plus-code software factory workflows."
    )


def test_canonical_skill_is_portable():
    metadata = _frontmatter(ROOT / "skills/sssf/SKILL.md")
    assert set(metadata) <= {
        "name", "description", "license", "compatibility", "metadata", "allowed-tools"
    }
    assert metadata["name"] == "sssf"
    assert metadata["description"] == (
        "Install and operate SSSF when creating, running, updating, or observing "
        "deterministic AI developer workflows and their agent roster."
    )
    assert metadata["compatibility"] == (
        "Requires Python 3.11+, uv, git, sqlite3, and GitHub Copilot authentication. "
        "Bun is optional for the visualizer."
    )
    assert metadata["metadata"]["author"] == "bossjones"
    assert metadata["metadata"]["version"] == "1.0.0"
    assert not (ROOT / ".claude/skills/sssf").exists()
