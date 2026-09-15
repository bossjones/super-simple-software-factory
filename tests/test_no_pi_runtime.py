from pathlib import Path

FORBIDDEN = (
    "agent_pi",
    "PiRequest",
    "PiResult",
    "PI_PATH",
    "PI_MODELS_PATH",
    "coding_agent: pi",
    "pi --mode",
)


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
