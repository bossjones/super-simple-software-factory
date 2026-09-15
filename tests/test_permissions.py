from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from adw_modules import permissions
from adw_modules.data_types import (
    AgentConfig,
    ConfigDefaults,
    PromptEngineering,
    SSSFConfig,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup_repo(tmp_path: Path) -> tuple[SimpleNamespace, AgentConfig]:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "tests@example.invalid")
    _git(tmp_path, "config", "user.name", "SSSF tests")
    agent = AgentConfig(
        name="builder",
        prompt_engineering=PromptEngineering(system="", user=""),
        writes=["allowed/"],
    )
    cfg = SSSFConfig(
        defaults=ConfigDefaults(protected_files=["protected.txt", "protected/"]),
        agents=[agent],
    )
    return SimpleNamespace(repo_root=tmp_path, cfg=cfg), agent


def _commit(repo: Path, *paths: str) -> None:
    _git(repo, "add", *paths)
    _git(repo, "commit", "-qm", "baseline")


def _enforce(
    run: SimpleNamespace,
    agent: AgentConfig,
    before: permissions.Snapshot,
) -> None:
    with pytest.raises(permissions.PermissionBreach):
        permissions.enforce(run, None, agent, before)


def test_same_size_same_line_rewrite_restores_staged_and_unstaged_content(
    tmp_path: Path,
):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected.txt"
    _write(protected, "committed\n")
    _commit(tmp_path, "protected.txt")
    _write(protected, "staged user value\n")
    _git(tmp_path, "add", "protected.txt")
    _write(protected, "operator-version\n")
    before = permissions.snapshot(run)

    _write(protected, "intruder-version\n")
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"operator-version\n"
    assert _git(tmp_path, "show", ":protected.txt") == "staged user value\n"
    assert _git(tmp_path, "diff", "--name-only").splitlines() == ["protected.txt"]
    assert _git(tmp_path, "diff", "--cached", "--name-only").splitlines() == ["protected.txt"]


def test_preexisting_untracked_rewrite_restores_exact_bytes_and_mode(tmp_path: Path):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected" / "operator.bin"
    protected.parent.mkdir()
    protected.write_bytes(b"\x00operator-secret\n")
    protected.chmod(0o600)
    before = permissions.snapshot(run)

    protected.write_bytes(b"\x00intruder-secret\n")
    protected.chmod(0o644)
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"\x00operator-secret\n"
    assert stat.S_IMODE(protected.stat().st_mode) == 0o600


def test_deleted_preexisting_untracked_file_is_restored(tmp_path: Path):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected" / "operator.txt"
    _write(protected, "keep my work\n")
    before = permissions.snapshot(run)

    protected.unlink()
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"keep my work\n"


def test_preexisting_untracked_symlink_type_change_restores_link(tmp_path: Path):
    run, agent = _setup_repo(tmp_path)
    target = tmp_path / "target.txt"
    _write(target, "outside the protected path\n")
    protected = tmp_path / "protected" / "operator-link"
    protected.parent.mkdir()
    protected.symlink_to("../target.txt")
    before = permissions.snapshot(run)

    protected.unlink()
    protected.write_text("replacement file\n")
    _enforce(run, agent, before)

    assert protected.is_symlink()
    assert os.readlink(protected) == "../target.txt"


def test_mode_change_to_clean_tracked_file_is_detected_and_restored(tmp_path: Path):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected.txt"
    _write(protected, "committed\n")
    protected.chmod(0o644)
    _commit(tmp_path, "protected.txt")
    before = permissions.snapshot(run)

    protected.chmod(0o755)
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"committed\n"
    assert stat.S_IMODE(protected.stat().st_mode) == 0o644
    assert _git(tmp_path, "status", "--short") == ""


def test_rename_and_new_unauthorized_files_are_rolled_back(tmp_path: Path):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected.txt"
    moved = tmp_path / "moved.txt"
    rogue = tmp_path / "rogue.txt"
    _write(protected, "committed\n")
    _commit(tmp_path, "protected.txt")
    before = permissions.snapshot(run)

    protected.rename(moved)
    _write(rogue, "new unauthorized file\n")
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"committed\n"
    assert not moved.exists()
    assert not rogue.exists()
    assert _git(tmp_path, "status", "--short") == ""


def test_breach_keeps_authorized_write_and_unrelated_preexisting_dirt(tmp_path: Path):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected.txt"
    unrelated = tmp_path / "notes.txt"
    allowed = tmp_path / "allowed" / "result.txt"
    _write(protected, "protected baseline\n")
    _write(unrelated, "committed notes\n")
    _commit(tmp_path, "protected.txt", "notes.txt")
    _write(unrelated, "operator notes\n")
    before = permissions.snapshot(run)

    _write(protected, "unauthorized\n")
    _write(allowed, "authorized result\n")
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"protected baseline\n"
    assert unrelated.read_bytes() == b"operator notes\n"
    assert allowed.read_bytes() == b"authorized result\n"
    assert _git(tmp_path, "status", "--short").splitlines() == [
        " M notes.txt",
        "?? allowed/",
    ]


@pytest.mark.parametrize(
    ("flag", "listing_tag"),
    [
        ("--skip-worktree", "S"),
        ("--assume-unchanged", "h"),
    ],
)
def test_hidden_tracked_rewrite_is_detected_restored_with_index_flag(
    tmp_path: Path,
    flag: str,
    listing_tag: str,
):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected.txt"
    _write(protected, "committed\n")
    _commit(tmp_path, "protected.txt")
    _git(tmp_path, "update-index", flag, "protected.txt")
    before = permissions.snapshot(run)

    _write(protected, "unauthorized\n")
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"committed\n"
    assert _git(tmp_path, "ls-files", "-v", "protected.txt").startswith(f"{listing_tag} ")


def test_intent_to_add_state_is_restored_after_breach(tmp_path: Path):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected.txt"
    _write(protected, "operator draft\n")
    _git(tmp_path, "add", "--intent-to-add", "protected.txt")
    before = permissions.snapshot(run)

    _write(protected, "unauthorized\n")
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"operator draft\n"
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""
    assert _git(tmp_path, "diff", "--name-only").splitlines() == ["protected.txt"]


def test_snapshot_rejects_submodules_without_touching_their_content(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-q")
    _git(source, "config", "user.email", "tests@example.invalid")
    _git(source, "config", "user.name", "SSSF tests")
    _write(source / "tracked.txt", "submodule baseline\n")
    _commit(source, "tracked.txt")

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    run, _agent = _setup_repo(worktree)
    _git(
        worktree,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(source),
        "protected-submodule",
    )
    _commit(worktree, ".gitmodules", "protected-submodule")
    sentinel = worktree / "protected-submodule" / "operator-draft.txt"
    _write(sentinel, "preserve me\n")

    with pytest.raises(permissions.PermissionBreach, match="submodules are unsupported"):
        permissions.snapshot(run)

    assert sentinel.read_bytes() == b"preserve me\n"
    assert (worktree / "protected-submodule" / ".git").is_file()


def test_introduced_gitlink_cannot_disable_other_rollbacks(tmp_path: Path):
    run, agent = _setup_repo(tmp_path)
    protected = tmp_path / "protected.txt"
    _write(protected, "committed\n")
    _commit(tmp_path, "protected.txt")
    before = permissions.snapshot(run)

    nested = tmp_path / "rogue-submodule"
    nested.mkdir()
    _git(nested, "init", "-q")
    _git(nested, "config", "user.email", "tests@example.invalid")
    _git(nested, "config", "user.name", "SSSF tests")
    sentinel = nested / "sentinel.txt"
    _write(sentinel, "preserve nested content\n")
    _commit(nested, "sentinel.txt")

    _write(protected, "unauthorized\n")
    commit = _git(nested, "rev-parse", "HEAD").strip()
    _git(
        tmp_path,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{commit},rogue-submodule",
    )
    _enforce(run, agent, before)

    assert protected.read_bytes() == b"committed\n"
    assert _git(tmp_path, "ls-files", "rogue-submodule") == ""
    assert not nested.exists()


def test_snapshot_rejects_untracked_embedded_repository(tmp_path: Path):
    run, _agent = _setup_repo(tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    _git(nested, "init", "-q")
    _git(nested, "config", "user.email", "tests@example.invalid")
    _git(nested, "config", "user.name", "SSSF tests")
    sentinel = nested / "sentinel.txt"
    _write(sentinel, "operator work\n")
    _commit(nested, "sentinel.txt")

    with pytest.raises(
        permissions.PermissionBreach,
        match="embedded Git repositories are unsupported",
    ):
        permissions.snapshot(run)

    assert sentinel.read_bytes() == b"operator work\n"
    assert (nested / ".git").is_dir()
