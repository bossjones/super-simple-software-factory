import json
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/sssf"
LOCAL_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


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
    metadata = _frontmatter(SKILL_ROOT / "SKILL.md")
    assert set(metadata) <= {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "allowed-tools",
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
    assert SKILL_ROOT.name == metadata["name"]
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"])
    assert len(metadata["description"]) <= 1024
    assert all(isinstance(value, str) for value in metadata["metadata"].values())
    assert not (ROOT / ".claude/skills/sssf").exists()


def test_canonical_skill_resources_exist():
    required = (
        SKILL_ROOT / "scripts/install.py",
        SKILL_ROOT / "scripts/make_adw.py",
        SKILL_ROOT / "scripts/make_config.py",
        SKILL_ROOT / "templates/adws",
        SKILL_ROOT / "templates/prompt_engineering",
        SKILL_ROOT / "templates/sssf.config.yaml",
        SKILL_ROOT / "templates/env.sample",
        SKILL_ROOT / "templates/justfile",
    )
    assert all(path.exists() for path in required)

    markdown = [
        SKILL_ROOT / "SKILL.md",
        *sorted((SKILL_ROOT / "cookbooks").glob("*.md")),
        *sorted((SKILL_ROOT / "references").glob("*.md")),
    ]
    assert markdown
    missing = []
    for source in markdown:
        for target in LOCAL_LINK.findall(source.read_text()):
            parsed = urlparse(target)
            if parsed.scheme or target.startswith("#"):
                continue
            resolved = (source.parent / parsed.path).resolve()
            if not resolved.is_relative_to(SKILL_ROOT.resolve()) or not resolved.exists():
                missing.append(f"{source.relative_to(ROOT)} -> {target}")
    assert missing == []


def test_agents_skill_symlink_exposes_canonical_skill():
    link = ROOT / ".agents/skills/sssf"
    assert link.is_symlink()
    assert link.readlink() == Path("../../skills/sssf")
    assert link.resolve() == SKILL_ROOT.resolve()
    assert _frontmatter(link / "SKILL.md")["name"] == "sssf"
