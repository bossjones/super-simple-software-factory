import re
from pathlib import Path
from urllib.parse import urlparse

FORBIDDEN = (
    "agent_pi",
    "PiRequest",
    "PiResult",
    "PI_PATH",
    "PI_MODELS_PATH",
    "coding_agent: pi",
    "pi --mode",
)

STALE_CURRENT_DOC_REFERENCES = (
    "../.claude/",
    ".claude/skills/sssf",
    "agent_pi",
    "harness_engineering",
    "coding_agent: pi",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_production_runtime_has_no_pi_coupling(repo_root: Path):
    roots = [
        repo_root / "skills/sssf/templates",
        repo_root / "skills/sssf/scripts",
        repo_root / "skills/sssf/SKILL.md",
        repo_root / "skills/sssf/references",
        repo_root / "skills/sssf/cookbooks",
        repo_root / "README.md",
    ]
    offenders = []
    for root in roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in {".py", ".md", ".yaml", ".yml", ".ts"}:
                continue
            text = path.read_text(errors="ignore")
            for needle in FORBIDDEN:
                if needle in text:
                    offenders.append(f"{path.relative_to(repo_root)}: {needle}")
    assert offenders == []


def test_current_ai_docs_do_not_reference_removed_sssf_surfaces(repo_root: Path):
    offenders = []
    current_docs = [
        *sorted((repo_root / "ai_docs").glob("*.md")),
        *sorted((repo_root / "images").glob("*.svg")),
    ]
    for path in current_docs:
        text = path.read_text()
        if "historical: true" in text:
            continue
        for needle in STALE_CURRENT_DOC_REFERENCES:
            if needle in text:
                offenders.append(f"{path.relative_to(repo_root)}: {needle}")
    assert offenders == []


def test_current_ai_docs_local_links_resolve(repo_root: Path):
    missing = []
    for path in sorted((repo_root / "ai_docs").glob("*.md")):
        text = path.read_text()
        if "historical: true" in text:
            continue
        for target in MARKDOWN_LINK.findall(text):
            parsed = urlparse(target)
            if parsed.scheme or target.startswith("#"):
                continue
            resolved = (path.parent / parsed.path).resolve()
            if not resolved.exists():
                missing.append(f"{path.relative_to(repo_root)} -> {target}")
    assert missing == []
