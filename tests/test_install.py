from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _install_command(repo_root: Path) -> list[str]:
    return ["uv", "run", str(repo_root / "skills/sssf/scripts/install.py")]


def _init_target_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)


LEGACY_FIXTURES = {
    "adws/adw_modules/agent_pi.py": "agent_pi.py",
    "adws/adw_modules/agent_cc.py": "agent_cc.py",
    "adws/adw_data/harness_engineering/subagents.ts": "subagents.ts",
    "adws/adw_data/harness_engineering/themeMap.ts": "themeMap.ts",
}


def _legacy_file(repo_root: Path, relative: str) -> bytes:
    fixture = repo_root / "tests/fixtures/legacy-install" / LEGACY_FIXTURES[relative]
    return fixture.read_bytes()


def test_install_stamps_copilot_factory(repo_root: Path, tmp_path: Path):
    _init_target_repo(tmp_path)

    result = subprocess.run(
        _install_command(repo_root),
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )

    assert (tmp_path / "adws/adw_modules/agent_copilot.py").is_file()
    assert not (tmp_path / "adws/adw_modules/agent_pi.py").exists()
    assert not (tmp_path / "adws/adw_data/harness_engineering").exists()
    assert not (tmp_path / "adws/adw_data/sessions").exists()
    assert not (tmp_path / "adws/adw_data/sssf.db").exists()
    gitignore = (tmp_path / ".gitignore").read_text()
    assert "adws/adw_data/sessions/" in gitignore
    assert "adws/adw_data/sssf.db*" in gitignore
    env_sample = (tmp_path / ".env.sample").read_text()
    assert "copilot" in env_sample.lower()
    assert "exact order" in env_sample
    assert "Set at most one token variable" in env_sample
    assert env_sample.index("#   1. COPILOT_GITHUB_TOKEN") < env_sample.index("#   2. GH_TOKEN")
    assert env_sample.index("#   2. GH_TOKEN") < env_sample.index("#   3. GITHUB_TOKEN")
    assert "copilot login" in env_sample
    assert "gh auth login" in env_sample
    assert "never commit credentials" in env_sample
    assert "just obs" not in result.stdout
    assert "just demo" in result.stdout


def test_second_install_skips_existing_files(repo_root: Path, tmp_path: Path):
    _init_target_repo(tmp_path)
    command = _install_command(repo_root)
    subprocess.run(command, cwd=tmp_path, check=True)
    target = tmp_path / "adws/adw_modules/agent_copilot.py"
    target.write_text("# local customization\n")

    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, check=True)

    assert target.read_text() == "# local customization\n"
    assert "skipped (already exist" in result.stdout


def test_force_install_overwrites_stamped_files(repo_root: Path, tmp_path: Path):
    _init_target_repo(tmp_path)
    command = _install_command(repo_root)
    subprocess.run(command, cwd=tmp_path, check=True)
    target = tmp_path / "adws/adw_modules/agent_copilot.py"
    target.write_text("# local customization\n")

    subprocess.run([*command, "--force"], cwd=tmp_path, check=True)

    assert target.read_text() != "# local customization\n"


def test_force_install_removes_factory_managed_legacy_files(
    repo_root: Path,
    tmp_path: Path,
):
    _init_target_repo(tmp_path)
    for relative in LEGACY_FIXTURES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_legacy_file(repo_root, relative))

    result = subprocess.run(
        [*_install_command(repo_root), "--force"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )

    assert not (tmp_path / "adws/adw_modules/agent_pi.py").exists()
    assert not (tmp_path / "adws/adw_modules/agent_cc.py").exists()
    assert not (tmp_path / "adws/adw_data/harness_engineering").exists()
    assert "removed legacy factory files: 4" in result.stdout


def test_force_install_preserves_customized_legacy_files(repo_root: Path, tmp_path: Path):
    _init_target_repo(tmp_path)
    customized = {}
    for source in LEGACY_FIXTURES:
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        content = f"# local customization for {target.name}\n".encode()
        target.write_bytes(content)
        customized[target] = content

    result = subprocess.run(
        [*_install_command(repo_root), "--force"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )

    for target, content in customized.items():
        assert target.read_bytes() == content
    assert "preserved customized legacy files" in result.stdout


def test_force_install_preserves_legacy_harness_symlink(repo_root: Path, tmp_path: Path):
    _init_target_repo(tmp_path)
    target = tmp_path / "custom-harness"
    target.mkdir()
    harness = tmp_path / "adws/adw_data/harness_engineering"
    harness.parent.mkdir(parents=True)
    harness.symlink_to(target, target_is_directory=True)

    result = subprocess.run(
        [*_install_command(repo_root), "--force"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )

    assert harness.is_symlink()
    assert harness.resolve() == target
    assert "preserved legacy symlinks" in result.stdout


@pytest.mark.parametrize("force", [False, True])
def test_install_preserves_destination_file_symlink(repo_root: Path, tmp_path: Path, force: bool):
    _init_target_repo(tmp_path)
    external = tmp_path / "external-agent.py"
    external.write_text("external content\n")
    target = tmp_path / "adws/adw_modules/agent_copilot.py"
    target.parent.mkdir(parents=True)
    target.symlink_to(external)

    command = _install_command(repo_root) + (["--force"] if force else [])
    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, check=True)

    assert target.is_symlink()
    assert target.resolve() == external
    assert external.read_text() == "external content\n"
    assert "preserved destination symlinks" in result.stdout


@pytest.mark.parametrize("force", [False, True])
def test_install_preserves_gitignore_symlink(repo_root: Path, tmp_path: Path, force: bool):
    _init_target_repo(tmp_path)
    external = tmp_path / "external-gitignore"
    external.write_text("external content\n")
    target = tmp_path / ".gitignore"
    target.symlink_to(external)

    command = _install_command(repo_root) + (["--force"] if force else [])
    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, check=True)

    assert target.is_symlink()
    assert target.resolve() == external
    assert external.read_text() == "external content\n"
    assert "preserved destination symlinks" in result.stdout


@pytest.mark.parametrize("directory_name", ["adw_modules", "adw_data"])
@pytest.mark.parametrize("force", [False, True])
def test_install_preserves_destination_directory_symlink(
    repo_root: Path, tmp_path: Path, directory_name: str, force: bool
):
    _init_target_repo(tmp_path)
    external = tmp_path / "external-modules"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_text("external content\n")
    target = tmp_path / "adws" / directory_name
    target.parent.mkdir(parents=True)
    target.symlink_to(external, target_is_directory=True)

    command = _install_command(repo_root) + (["--force"] if force else [])
    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, check=True)

    assert target.is_symlink()
    assert target.resolve() == external
    assert sentinel.read_text() == "external content\n"
    assert "preserved destination symlinks" in result.stdout


def test_adw_entry_points_pin_copilot_sdk(repo_root: Path):
    expected = (
        "# dependencies = [\n"
        '#   "github-copilot-sdk==1.0.13",\n'
        '#   "pydantic",\n'
        '#   "python-dotenv",\n'
        '#   "pyyaml",\n'
        '#   "rich",\n'
        "# ]"
    )
    entry_points = sorted((repo_root / "skills/sssf/templates/adws").glob("adw_*.py"))

    assert entry_points
    for path in entry_points:
        assert path.read_text().count(expected) == 1, path


def test_generated_justfile_doctor_runs_in_fresh_install(repo_root: Path, tmp_path: Path):
    _init_target_repo(tmp_path)
    subprocess.run(_install_command(repo_root), cwd=tmp_path, check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    copilot = bin_dir / "copilot"
    copilot.write_text("#!/bin/sh\necho 'GitHub Copilot CLI test-version'\n")
    copilot.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        ["just", "copilot-doctor"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "GitHub Copilot CLI test-version" in result.stdout
    assert "1.0.13" in result.stdout
    assert "Runtime cached at:" in result.stdout or "already cached" in result.stdout
    assert "obs:" not in (tmp_path / "justfile").read_text()
