#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///
"""/install — stamp the Copilot-native SSSF factory into the cwd. Idempotent.

Usage:
    uv run <skill>/scripts/install.py [--force]

Stamps: adws/ (Copilot SDK modules + starter ADWs),
adws/adw_data/prompt_engineering/ (4 starter agents),
adws/adw_sssf_config/sssf.config.yaml, .env.sample, .gitignore entries.
Existing files are skipped unless --force.
"""

import argparse
import hashlib
import os
import shutil
import sys
import uuid
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

GITIGNORE_ENTRIES = [
    "adws/adw_data/sessions/",
    "adws/adw_data/sssf.db*",
    ".env",
    # The ADWs are Python, so importing adw_modules writes bytecode next to it.
    # Chains that end in a commit phase call `git add -A`, so without this a
    # stamped repo commits its own .pyc files — 15 of them showed up in the
    # first repo that was ever installed into from scratch.
    "__pycache__/",
    "*.pyc",
]

LEGACY_STAMPED_SHA256 = {
    "adws/adw_modules/" + "agent_" + "pi.py": (
        "bbf254f016aefa7e61d08dbfe08fe7d87f1f0359b36299e84c35cf4193fea945"
    ),
    "adws/adw_modules/agent_cc.py": (
        "8e2dbc70258eda8f63612bdeb94522911fd632d000ea0e3cbff8f7ba35059d63"
    ),
    "adws/adw_data/harness_engineering/subagents.ts": (
        "6f5a01145cde8f1d3a31d0c65da53aa06da54ce382ccc97d5d9685f05740ed17"
    ),
    "adws/adw_data/harness_engineering/themeMap.ts": (
        "827dfc100c7ce666d650b31542e03c047deee6543a2979f071ddc78d4531cd8b"
    ),
}


def _copy_file(src: Path, dest: Path) -> None:
    """Copy to a sibling and replace the destination, never dereferencing it."""
    temporary = dest.with_name(f".{dest.name}.sssf-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        shutil.copy2(src, temporary)
        os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)


def _symlink_component(path: Path) -> Path | None:
    current = path
    while current != current.parent:
        if current.is_symlink():
            return current
        current = current.parent
    return None


def stamp(
    src: Path,
    dest: Path,
    force: bool,
    stamped: list,
    skipped: list,
    preserved: list | None = None,
) -> None:
    if preserved is None:
        preserved = []
    symlink = _symlink_component(dest)
    if symlink is not None:
        if str(symlink) not in preserved:
            preserved.append(str(symlink))
        return
    if src.is_dir():
        for child in sorted(src.iterdir()):
            if child.name == "__pycache__":
                continue
            stamp(child, dest / child.name, force, stamped, skipped, preserved)
        return
    if dest.exists() and not force:
        skipped.append(str(dest))
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    _copy_file(src, dest)
    stamped.append(str(dest))


def ensure_gitignore(root: Path, stamped: list, preserved: list | None = None) -> None:
    if preserved is None:
        preserved = []
    gitignore = root / ".gitignore"
    symlink = _symlink_component(gitignore)
    if symlink is not None:
        if str(symlink) not in preserved:
            preserved.append(str(symlink))
        return
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    missing = [e for e in GITIGNORE_ENTRIES if e not in existing]
    if missing:
        with gitignore.open("a") as f:
            f.write("\n# sssf runtime\n" + "\n".join(missing) + "\n")
        stamped.append(f"{gitignore} (+{len(missing)} entries)")


def cleanup_legacy(
    root: Path, removed: list, preserved: list, preserved_symlinks: list | None = None
) -> None:
    """Remove only byte-for-byte factory-managed files from older installs."""
    for relative, expected_hash in LEGACY_STAMPED_SHA256.items():
        path = root / relative
        symlink = _symlink_component(path)
        if symlink is not None:
            target = preserved_symlinks if preserved_symlinks is not None else preserved
            if str(symlink) not in target:
                target.append(str(symlink))
            continue
        if not path.is_file() or path.is_symlink():
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash == expected_hash:
            path.unlink()
            removed.append(str(path))
        else:
            preserved.append(str(path))

    harness_dir = root / "adws" / "adw_data" / "harness_engineering"
    symlink = _symlink_component(harness_dir)
    if symlink is not None:
        target = preserved_symlinks if preserved_symlinks is not None else preserved
        if str(symlink) not in target:
            target.append(str(symlink))
    elif harness_dir.is_dir() and not any(harness_dir.iterdir()):
        harness_dir.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    root = Path.cwd()
    stamped, skipped = [], []

    preserved = []
    stamp(TEMPLATES / "adws", root / "adws", args.force, stamped, skipped, preserved)
    stamp(
        TEMPLATES / "prompt_engineering",
        root / "adws" / "adw_data" / "prompt_engineering",
        args.force,
        stamped,
        skipped,
        preserved,
    )
    stamp(
        TEMPLATES / "sssf.config.yaml",
        root / "adws" / "adw_sssf_config" / "sssf.config.yaml",
        args.force,
        stamped,
        skipped,
        preserved,
    )
    stamp(
        TEMPLATES / "env.sample",
        root / ".env.sample",
        args.force,
        stamped,
        skipped,
        preserved,
    )
    # The recipes are part of the operating experience, and several cookbooks
    # plus the run banner tell you to use them, so a stamped repo has to have
    # them. Skipped like any other file if the repo already has a justfile.
    stamp(TEMPLATES / "justfile", root / "justfile", args.force, stamped, skipped, preserved)
    removed_legacy, preserved_legacy = [], []
    preserved_legacy_symlinks = []
    if args.force:
        cleanup_legacy(root, removed_legacy, preserved_legacy, preserved_legacy_symlinks)
    ensure_gitignore(root, stamped, preserved)

    print(f"sssf Copilot factory installed into {root}")
    print(f"  stamped: {len(stamped)} file(s)")
    for s in stamped:
        print(f"    + {s}")
    if skipped:
        print(f"  skipped (already exist, use --force to overwrite): {len(skipped)}")
    if removed_legacy:
        print(f"  removed legacy factory files: {len(removed_legacy)}")
        for path in removed_legacy:
            print(f"    - {path}")
    if preserved_legacy:
        print("  preserved customized legacy files (remove manually if desired):")
        for path in preserved_legacy:
            print(f"    ! {path}")
    if preserved_legacy_symlinks:
        print("  preserved legacy symlinks:")
        for path in preserved_legacy_symlinks:
            print(f"    ! {path}")
    if preserved:
        print("  preserved destination symlinks:")
        for path in preserved:
            print(f"    ! {path}")
    print("\nnext steps:")
    print("  1. cp .env.sample .env   # then set the key(s) your roster needs")
    print("  2. just demo             # two cheap read-only runs, end to end")
    print("  3. just sessions         # what just happened")
    print("\n  no just? the raw form of step 2 is:")
    print('     uv run adws/adw_prompt.py "say hello" --agent scout')
    return 0


if __name__ == "__main__":
    sys.exit(main())
