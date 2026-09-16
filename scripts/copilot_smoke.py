"""Run an opt-in authenticated smoke test against the Copilot runtime."""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ADW_ROOT = ROOT / "skills/sssf/templates/adws"
if str(ADW_ROOT) not in sys.path:
    sys.path.insert(0, str(ADW_ROOT))

from adw_modules import agent_copilot, agents  # noqa: E402
from adw_modules.data_types import (  # noqa: E402
    AgentCallbacks,
    AgentRequest,
    GenericOutput,
)

RESUMED_SUMMARY = "smoke-resumed"
TOKEN_ENV_NAMES = (
    "COPILOT_GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)


def _command_version(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    if result.returncode != 0:
        return "unavailable"
    return next(
        (line.strip() for line in result.stdout.splitlines() if line.strip()), "unavailable"
    )


def _safe_failure(error: Exception) -> str:
    message = str(error).replace("\n", " ").strip() or type(error).__name__
    for name in TOKEN_ENV_NAMES:
        token = os.environ.get(name)
        if token:
            message = message.replace(token, "[redacted]")
    return message


def _expected_output(summary: str) -> dict[str, Any]:
    return {
        "status": "success",
        "summary": summary,
        "artifacts": [],
        "notes_for_next_agent": "",
    }


def _create_repository(repo: Path, marker: str) -> None:
    repo.mkdir(parents=True)
    commands = (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "smoke@example.invalid"],
        ["git", "config", "user.name", "SSSF Smoke"],
    )
    for command in commands:
        subprocess.run(command, cwd=repo, check=True)
    (repo / "README.md").write_text(f"{marker}\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)


def _request(
    repo: Path,
    *,
    session_id: str,
    prompt: str,
    resume: bool,
) -> AgentRequest:
    return AgentRequest(
        prompt=prompt,
        system_prompt="Follow the requested JSON contract.",
        model=os.environ.get("SSSF_SMOKE_MODEL", "gpt-5.4"),
        reasoning_effort="low",
        context_tier="default",
        session_id=session_id,
        resume=resume,
        runtime_dir=str(repo / ".copilot-runtime"),
        raw_output_path=str(repo / "events.jsonl"),
        tools=["view"],
        timeout_seconds=300,
        cwd=str(repo),
    )


def _validate_output(text: str, expected: dict[str, Any]) -> GenericOutput:
    payload: dict[str, Any] = agents._extract_json(text)
    expected_fields = set(GenericOutput.model_fields)
    if set(payload) != expected_fields:
        raise ValueError(
            f"response fields {sorted(payload)} do not match GenericOutput "
            f"{sorted(expected_fields)}"
        )
    output = GenericOutput.model_validate(payload)
    if output.model_dump() != expected:
        raise ValueError("response did not match the requested smoke envelope")
    return output


def _raw_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main(workspace_root: Path | None = None) -> int:
    """Run the smoke in an isolated repository beneath the project cache."""
    sdk_version = importlib.metadata.version("github-copilot-sdk")
    cli_version = _command_version(["copilot", "--version"])
    print(f"sdk-version: {sdk_version}")
    print(f"cli-version: {cli_version}")

    parent = workspace_root or ROOT / ".cache"
    parent.mkdir(parents=True, exist_ok=True)
    repo = parent / f"copilot-smoke-{uuid.uuid4()}"
    try:
        marker = f"marker-{uuid.uuid4().hex}"
        session_id = f"sssf-smoke-{uuid.uuid4()}"
        _create_repository(repo, marker)

        first_expected = _expected_output(marker)
        first_request = _request(
            repo,
            session_id=session_id,
            resume=False,
            prompt=(
                "First use the view tool to read README.md. After the tool completes, "
                "return only this exact JSON object: "
                f"{json.dumps(first_expected, separators=(',', ':'))}"
            ),
        )
        first_result = agent_copilot.run(first_request, AgentCallbacks())
        _validate_output(first_result.text, first_expected)
        if first_result.session_id != session_id:
            raise RuntimeError("Copilot runtime returned a different session ID")
        raw_output = Path(first_request.raw_output_path)
        if not raw_output.is_file():
            raise RuntimeError("Copilot runtime did not capture any session events")
        first_events = _raw_events(raw_output)
        if not first_events:
            raise RuntimeError("Copilot runtime did not capture any session events")
        if not any(
            str(event.get("type", "")).startswith("tool.execution") for event in first_events
        ):
            raise RuntimeError("read-only turn did not record a view tool event")
        if first_result.runtime is None:
            raise RuntimeError("Copilot runtime did not report version metadata")
        print(f"runtime-version: {first_result.runtime.runtime_version}")
        print(f"protocol-version: {first_result.runtime.protocol_version}")
        print("read-only-turn-status: success")

        resumed_expected = _expected_output(RESUMED_SUMMARY)
        resumed_request = _request(
            repo,
            session_id=session_id,
            resume=True,
            prompt=(
                "Correction turn: replace the prior summary. Return only "
                f"{json.dumps(resumed_expected, separators=(',', ':'))}"
            ),
        )
        resumed_result = agent_copilot.run(resumed_request, AgentCallbacks())
        _validate_output(resumed_result.text, resumed_expected)
        if resumed_result.session_id != session_id:
            raise RuntimeError("Copilot resume returned a different session ID")
        resumed_events = _raw_events(raw_output)
        if len(resumed_events) <= len(first_events):
            raise RuntimeError("resumed turn did not append session events")
        print("resume-turn-status: success")
        print("smoke-status: success")
        return 0
    except Exception as error:
        print(f"smoke-status: failed ({_safe_failure(error)})", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
