from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from adw_modules.data_types import AgentResult, RuntimeInfo


def _load_smoke(repo_root: Path) -> ModuleType:
    path = repo_root / "scripts/copilot_smoke.py"
    spec = importlib.util.spec_from_file_location("copilot_smoke", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_builds_current_request_and_validates_exact_envelope(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    smoke = _load_smoke(repo_root)
    requests: list[Any] = []

    def fake_run(request: Any, _callbacks: Any) -> AgentResult:
        requests.append(request)
        raw_path = Path(request.raw_output_path)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if request.resume:
            expected = smoke._expected_output(smoke.RESUMED_SUMMARY)
            event = {"type": "assistant.message"}
        else:
            marker = (Path(request.cwd) / "README.md").read_text().strip()
            expected = smoke._expected_output(marker)
            event = {"type": "tool.execution_complete", "data": {"tool_name": "view"}}
        with raw_path.open("a") as raw:
            raw.write(json.dumps(event) + "\n")
        return AgentResult(
            text=json.dumps(expected),
            session_id=request.session_id,
            runtime=RuntimeInfo(
                sdk_version="1.0.13",
                runtime_version="smoke-runtime",
                protocol_version="3",
                cli_version="copilot smoke-cli",
            ),
        )

    monkeypatch.setattr(smoke.agent_copilot, "run", fake_run)
    monkeypatch.setattr(smoke, "_command_version", lambda _command: "copilot smoke-cli")

    assert smoke.main(tmp_path) == 0

    assert len(requests) == 2
    first, resumed = requests
    assert [request.resume for request in requests] == [False, True]
    assert first.session_id == resumed.session_id
    assert first.reasoning_effort == "low"
    assert first.context_tier == "default"
    assert first.tools == ["view"]
    assert first.timeout_seconds == 300
    assert first.skill_directories == []
    assert first.plugin_directories == []
    assert first.mcp_servers == {}
    assert "use the view tool to read README.md" in first.prompt
    assert json.loads(resumed.prompt.split("Return only ", 1)[1]) == {
        "status": "success",
        "summary": "smoke-resumed",
        "artifacts": [],
        "notes_for_next_agent": "",
    }
    assert not any(tmp_path.iterdir())
    output = capsys.readouterr()
    assert output.err == ""
    assert "sdk-version: 1.0.13" in output.out
    assert "cli-version: copilot smoke-cli" in output.out
    assert "runtime-version: smoke-runtime" in output.out
    assert "protocol-version: 3" in output.out
    assert "read-only-turn-status: success" in output.out
    assert "resume-turn-status: success" in output.out
    assert "smoke-status: success" in output.out


def test_smoke_redacts_token_values_from_failures(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    smoke = _load_smoke(repo_root)
    token = "secret-token-value"

    def fake_run(_request: Any, _callbacks: Any) -> AgentResult:
        raise RuntimeError(f"authentication failed for {token}")

    monkeypatch.setattr(smoke.agent_copilot, "run", fake_run)
    monkeypatch.setattr(smoke, "_command_version", lambda _command: "copilot smoke-cli")
    monkeypatch.setenv("GH_TOKEN", token)

    assert smoke.main(tmp_path) == 1

    output = capsys.readouterr()
    assert token not in output.out
    assert token not in output.err
    assert "smoke-status: failed (authentication failed for [redacted])" in output.err
    assert not any(tmp_path.iterdir())
