"""What an agent may CHANGE, enforced in code after the fact.

`tools:` is a capability list, not a sandbox, and two holes make it
unenforceable on its own:

  * `bash` runs anything. A builder handed bash to run a test suite can also
    run `git checkout adws/` — which is not hypothetical: one did, discarding
    uncommitted changes to the very quality check it was about to be judged by.
  * `write` reaches any path, not just the one report file an agent was given
    it for. A reviewer configured with "no edit, so it cannot quietly fix"
    could still rewrite the code it was reviewing.

So permission is verified the way every other claim in this system is —
after the fact, against the repo itself. `snapshot()` fingerprints the working
tree's change-set before an agent runs; `enforce()` compares it afterwards and
fails the phase if the agent touched anything outside its allowlist.

Comparing change-sets, rather than watching for writes, is what catches the
`git checkout` case: a path that was modified before the agent ran and is clean
afterwards has been reverted, and a reversion is a modification. Appearing,
disappearing, and changing all count.

A breach is NOT a gate violation. Gates are for work an agent can be asked to
redo; a breach cannot be corrected by re-prompting, because the write already
happened. It aborts the phase and names every offending path.

Two keys drive it, both in sssf.config.yaml:
    defaults.protected_files   paths no agent may touch unless it names them itself
    agents[].writes      None = unrestricted · [] = read-only · [...] = only these
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .data_types import AgentConfig, SSSFConfig


class PermissionBreach(RuntimeError):
    """An agent modified a path it was not permitted to modify."""


@dataclass(frozen=True)
class IndexEntry:
    mode: str
    object_id: str
    stage: int


@dataclass(frozen=True)
class IndexFlags:
    assume_unchanged: bool = False
    intent_to_add: bool = False
    skip_worktree: bool = False


@dataclass(frozen=True)
class WorktreeState:
    kind: str
    mode: int | None
    digest: str | None
    content: bytes | None = field(repr=False)


@dataclass(frozen=True)
class Snapshot:
    index: dict[str, tuple[IndexEntry, ...]]
    index_flags: dict[str, IndexFlags]
    tracked_modes: dict[str, int]
    worktree: dict[str, WorktreeState]


def _git(args: list[str], cwd: Path, *, input_data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=input_data,
        capture_output=True,
    )
    if result.returncode != 0:
        command = " ".join(["git", *args])
        error = result.stderr.decode("utf-8", "replace").strip()
        raise PermissionBreach(f"permission boundary command failed: {command}: {error}")
    return result.stdout


def _decode_path(path: bytes) -> str:
    return path.decode("utf-8", "surrogateescape")


def _encode_path(path: str) -> bytes:
    return path.encode("utf-8", "surrogateescape")


def _nul_paths(output: bytes) -> set[str]:
    return {_decode_path(path).rstrip("/") for path in output.split(b"\0") if path}


def _dirty_paths(repo_root: Path) -> set[str]:
    paths: set[str] = set()
    commands = [
        ["diff", "--no-renames", "--name-only", "-z", "--"],
        ["diff", "--cached", "--no-renames", "--name-only", "-z", "--"],
        ["ls-files", "--others", "--exclude-standard", "-z", "--"],
    ]
    for command in commands:
        paths.update(_nul_paths(_git(command, repo_root)))
    return paths


def _index_snapshot(repo_root: Path) -> dict[str, tuple[IndexEntry, ...]]:
    entries: dict[str, list[IndexEntry]] = {}
    for record in _git(["ls-files", "--stage", "-z"], repo_root).split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        path = _decode_path(raw_path)
        entries.setdefault(path, []).append(
            IndexEntry(mode=mode, object_id=object_id, stage=int(stage))
        )
    return {path: tuple(path_entries) for path, path_entries in entries.items()}


def _index_flags(repo_root: Path) -> dict[str, IndexFlags]:
    flags: dict[str, IndexFlags] = {}
    output = _git(["ls-files", "--debug", "-z"], repo_root)
    while output:
        raw_path, output = output.split(b"\0", 1)
        metadata: list[bytes] = []
        for _ in range(5):
            line, output = output.split(b"\n", 1)
            metadata.append(line)
        raw_flags = int(metadata[-1].rsplit(b"flags: ", 1)[1], 16)
        path = _decode_path(raw_path)
        previous = flags.get(path, IndexFlags())
        flags[path] = IndexFlags(
            assume_unchanged=previous.assume_unchanged or bool(raw_flags & 0x8000),
            intent_to_add=previous.intent_to_add or bool(raw_flags & 0x20000000),
            skip_worktree=previous.skip_worktree or bool(raw_flags & 0x40000000),
        )
    return flags


def _kind(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISFIFO(mode):
        return "fifo"
    return "special"


def _exists(path: Path) -> bool:
    try:
        path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def _worktree_state(repo_root: Path, path: str) -> WorktreeState:
    absolute = repo_root / path
    try:
        metadata = absolute.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return WorktreeState(kind="missing", mode=None, digest=None, content=None)

    kind = _kind(metadata.st_mode)
    content: bytes | None = None
    if kind == "file":
        content = absolute.read_bytes()
    elif kind == "symlink":
        content = os.fsencode(os.readlink(absolute))
    digest = hashlib.sha256(content).hexdigest() if content is not None else None
    return WorktreeState(
        kind=kind,
        mode=stat.S_IMODE(metadata.st_mode),
        digest=digest,
        content=content,
    )


def _tracked_modes(repo_root: Path, index: dict[str, tuple[IndexEntry, ...]]) -> dict[str, int]:
    modes: dict[str, int] = {}
    for path in index:
        try:
            modes[path] = stat.S_IMODE((repo_root / path).lstat().st_mode)
        except (FileNotFoundError, NotADirectoryError):
            continue
    return modes


def snapshot(run, *, reject_submodules: bool = True) -> Snapshot:
    """Capture the exact pre-call state needed for detection and restoration.

    Every tracked path and dirty untracked path retains its bytes, kind,
    symlink target, mode, index entries, and semantic index flags in memory.
    Reading tracked paths independently of Git's dirty filtering closes
    skip-worktree and assume-unchanged blind spots. Ignored paths remain
    outside the repository comparison, including the normal session runtime
    under `data_dir`.
    """
    repo_root = Path(run.repo_root)
    index = _index_snapshot(repo_root)
    dirty_paths = _dirty_paths(repo_root)
    submodules = sorted(
        path for path, entries in index.items() if any(entry.mode == "160000" for entry in entries)
    )
    if submodules and reject_submodules:
        paths = ", ".join(submodules)
        raise PermissionBreach(f"submodules are unsupported by the SSSF write boundary: {paths}")
    embedded_repositories = sorted(
        path
        for path in dirty_paths
        if (repo_root / path).is_dir() and _exists(repo_root / path / ".git")
    )
    if embedded_repositories and reject_submodules:
        paths = ", ".join(embedded_repositories)
        raise PermissionBreach(
            f"embedded Git repositories are unsupported by the SSSF write boundary: {paths}"
        )
    worktree = {path: _worktree_state(repo_root, path) for path in set(index) | dirty_paths}
    return Snapshot(
        index=index,
        index_flags=_index_flags(repo_root),
        tracked_modes=_tracked_modes(repo_root, index),
        worktree=worktree,
    )


def changed_paths(before: Snapshot, after: Snapshot) -> list[str]:
    """Every path whose worktree bytes/type/mode or index state changed."""
    candidates = (
        set(before.worktree)
        | set(after.worktree)
        | set(before.index)
        | set(after.index)
        | set(before.index_flags)
        | set(after.index_flags)
        | set(before.tracked_modes)
        | set(after.tracked_modes)
    )
    return sorted(
        path
        for path in candidates
        if before.worktree.get(path) != after.worktree.get(path)
        or before.index.get(path) != after.index.get(path)
        or before.index_flags.get(path) != after.index_flags.get(path)
        or before.tracked_modes.get(path) != after.tracked_modes.get(path)
    )


def _glob(pattern: str) -> re.Pattern:
    """Translate a pattern, with `*` stopping at a path separator.

    fnmatch would let `*` cross `/`, which quietly widens every pattern:
    `adws/adw_*.py` would match `adws/adw_data/sessions/x/y.py` as well as the
    ADW scripts it means. `**` is the way to say "cross directories".
    """
    out, i = [], 0
    while i < len(pattern):
        char = pattern[i]
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif char == "*":
            out.append("[^/]*")
            i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    return re.compile("".join(out))


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):  # directory prefix
        return path.startswith(pattern)
    if "*" in pattern or "?" in pattern:
        return _glob(pattern).fullmatch(path) is not None
    return path == pattern


def always_writable(cfg: SSSFConfig) -> list[str]:
    """The session runtime, which EVERY agent must be able to write.

    `context_handoff/` is the one place agents hand work to each other, and an
    agent's own prompts, raw_output.jsonl, and envelope.json land beside it.
    Scout writes its findings there, the reviewer its review, the planner its
    plan — a read-only agent is read-only with respect to the REPO, never with
    respect to its own report.

    This is granted from `data_dir` rather than left to .gitignore. The runtime
    is normally ignored, so it never even appears in a snapshot — but an agent's
    ability to record its work must not hang on a gitignore entry that someone
    can delete or that a changed `data_dir` can outgrow.
    """
    return [cfg.defaults.data_dir.rstrip("/") + "/"]


def permitted(path: str, agent: AgentConfig, cfg: SSSFConfig) -> bool:
    """Session runtime first, then the agent's own list, then what is protected."""
    if any(_matches(path, p) for p in always_writable(cfg)):
        return True
    if any(_matches(path, p) for p in (agent.writes or [])):
        return True  # naming a path is what unlocks a protected one
    if any(_matches(path, p) for p in cfg.defaults.protected_files):
        return False
    return agent.writes is None  # None = unrestricted, [] = no repo writes


def _remove_path(path: Path) -> None:
    try:
        metadata = path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return
    if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
        shutil.rmtree(path)
    else:
        path.unlink()


def _restore_index(
    repo_root: Path,
    path: str,
    entries: tuple[IndexEntry, ...],
    flags: IndexFlags,
) -> None:
    _git(["update-index", "--force-remove", "--", path], repo_root)
    if not entries:
        return
    if flags.intent_to_add:
        _git(["add", "--intent-to-add", "--", path], repo_root)
    else:
        raw_path = _encode_path(path)
        index_info = b"".join(
            f"{entry.mode} {entry.object_id} {entry.stage}\t".encode("ascii") + raw_path + b"\0"
            for entry in entries
        )
        _git(["update-index", "-z", "--index-info"], repo_root, input_data=index_info)
    if flags.assume_unchanged:
        _git(["update-index", "--assume-unchanged", "--", path], repo_root)
    if flags.skip_worktree:
        _git(["update-index", "--skip-worktree", "--", path], repo_root)


def _restore_worktree(path: Path, state: WorktreeState) -> None:
    _remove_path(path)
    if state.kind == "missing":
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if state.kind == "file":
        path.write_bytes(state.content or b"")
    elif state.kind == "symlink":
        os.symlink(os.fsdecode(state.content or b""), path)
    elif state.kind == "directory":
        path.mkdir()
    elif state.kind == "fifo":
        os.mkfifo(path)
    else:
        raise OSError("cannot recreate unsupported special file")

    if state.mode is not None and state.kind != "symlink":
        path.chmod(state.mode)


def _clean_worktree_state(
    repo_root: Path,
    path: str,
    entries: tuple[IndexEntry, ...],
    mode: int | None,
) -> WorktreeState:
    entry = next((candidate for candidate in entries if candidate.stage == 0), None)
    if entry is None:
        return WorktreeState(kind="missing", mode=None, digest=None, content=None)
    if entry.mode == "160000":
        raise OSError("cannot restore a changed submodule worktree")

    content = _git(["cat-file", "blob", entry.object_id], repo_root)
    kind = "symlink" if entry.mode == "120000" else "file"
    default_mode = 0o755 if entry.mode == "100755" else 0o644
    return WorktreeState(
        kind=kind,
        mode=mode if mode is not None else default_mode,
        digest=hashlib.sha256(content).hexdigest(),
        content=content,
    )


def _roll_back(run, path: str, before: Snapshot, after: Snapshot) -> str:
    """Restore one unauthorized path to its exact pre-call state."""
    repo_root = Path(run.repo_root)
    try:
        entries = before.index.get(path, ())
        if any(entry.mode == "160000" for entry in entries):
            raise OSError("cannot restore a changed submodule worktree")
        introduced_gitlink = not entries and any(
            entry.mode == "160000" for entry in after.index.get(path, ())
        )
        state = before.worktree.get(path)
        if state is None:
            state = _clean_worktree_state(
                repo_root,
                path,
                entries,
                before.tracked_modes.get(path),
            )
        preserve_gitlink_worktree = (
            introduced_gitlink and state.kind == "directory" and path in before.worktree
        )
        if not preserve_gitlink_worktree:
            _restore_worktree(repo_root / path, state)
        _restore_index(
            repo_root,
            path,
            entries,
            before.index_flags.get(path, IndexFlags()),
        )
    except (OSError, PermissionBreach) as error:
        return f"could not restore ({error})"
    if introduced_gitlink:
        if preserve_gitlink_worktree:
            return "removed introduced gitlink; preserved its pre-existing worktree directory"
        return "removed introduced gitlink and worktree"
    return "restored pre-call state" if path in before.worktree or entries else "deleted"


def enforce(run, phase, agent: AgentConfig, before: Snapshot) -> list[str]:
    """Compare the tree against `before`; undo and raise if the agent overstepped.

    Returns the paths it legitimately changed, so the trace records what an
    agent actually touched rather than only what it claimed in its envelope.

    Detection alone would leave the repo holding the unauthorized change while
    reporting a failure, so anything the agent introduced outside its allowlist
    is rolled back before the phase dies. What it cannot undo, it names.
    """
    after = snapshot(run, reject_submodules=False)
    touched = changed_paths(before, after)
    breaches = [p for p in touched if not permitted(p, agent, run.cfg)]
    if not breaches:
        return touched

    outcomes = {
        path: _roll_back(run, path, before, after)
        for path in sorted(breaches, key=lambda candidate: (candidate.count("/"), candidate))
    }
    scope = (
        "read-only"
        if agent.writes == []
        else f"limited to {agent.writes}"
        if agent.writes
        else f"barred from {run.cfg.defaults.protected_files}"
    )
    detail = "\n".join(f"  - {p} — {outcome}" for p, outcome in outcomes.items())
    raise PermissionBreach(
        f"{agent.name} is {scope} but modified {len(breaches)} path(s):\n{detail}"
    )
