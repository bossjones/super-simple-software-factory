from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from adw_modules import agents, permissions
from adw_modules.data_types import (
    AgentCall,
    AgentConfig,
    AgentEvent,
    AgentResult,
    EnvelopeBase,
    EventRecord,
    Phase,
    PhaseParams,
    PromptEngineering,
    RuntimeInfo,
    SSSFConfig,
    TimeoutConfig,
    UsageBreakdown,
)

REAL_PERMISSION_SNAPSHOT = permissions.snapshot
REAL_PERMISSION_ENFORCE = permissions.enforce


class FakeTracer:
    def __init__(self) -> None:
        self.events: list[EventRecord] = []
        self.gates: list[tuple[str, int]] = []
        self.envelopes: list[tuple[bool, int]] = []
        self.sessions: list[dict[str, Any]] = []

    def event(self, record: EventRecord) -> None:
        self.events.append(record)

    def gate_row(self, _phase: Phase, gate: str, _report: Any, attempt: int) -> None:
        self.gates.append((gate, attempt))

    def envelope_row(
        self,
        _phase: Phase,
        _agent: str,
        _output_type: str,
        _payload_json: str,
        valid: bool,
        attempt: int,
    ) -> None:
        self.envelopes.append((valid, attempt))

    def agent_session_row(
        self,
        _adw_id: str,
        agent: Any,
        session_id: str,
        *,
        context_tokens: int,
        context_window: int,
        runtime: RuntimeInfo | None = None,
    ) -> None:
        self.sessions.append(
            {
                "agent": agent.name,
                "coding_agent": agent.coding_agent,
                "session_id": session_id,
                "context_tokens": context_tokens,
                "context_window": context_window,
                "runtime": runtime,
            }
        )


class FakeConsole:
    def __init__(self) -> None:
        self.retries: list[tuple[str, int, int, str]] = []
        self.gates: list[str] = []
        self.started: list[tuple[str, str, str]] = []
        self.finished: list[tuple[str, int, float]] = []
        self.summaries: list[EnvelopeBase] = []

    def agent_started(self, name: str, model: str, session_id: str) -> None:
        self.started.append((name, model, session_id))

    def retry(self, name: str, attempt: int, limit: int, reason: str) -> None:
        self.retries.append((name, attempt, limit, reason))

    def gate_result(self, name: str, _report: Any) -> None:
        self.gates.append(name)

    def envelope_summary(self, envelope: EnvelopeBase) -> None:
        self.summaries.append(envelope)

    def agent_finished(self, name: str, tokens: int, cost: float) -> None:
        self.finished.append((name, tokens, cost))


class FakeRun:
    def __init__(
        self,
        tmp_path: Path,
        *,
        agent_map: dict[str, dict[str, str]] | None = None,
    ) -> None:
        system = tmp_path / "system.md"
        user = tmp_path / "user.md"
        system.write_text("You are precise. {{ prompt }}")
        user.write_text("Return a report for: {{ prompt }}")
        self.cfg = SSSFConfig(
            agents=[
                AgentConfig(
                    name="builder",
                    model="gpt-5.4",
                    reasoning_effort="high",
                    context_tier="long_context",
                    color="blue",
                    purpose="Implement the requested change",
                    prompt_engineering=PromptEngineering(system=str(system), user=str(user)),
                    tools=["view", "bash"],
                    skill_directories=["skills"],
                    plugin_directories=["plugins"],
                    mcp_servers={"zeta": {"type": "local"}, "alpha": {"type": "http"}},
                    writes=["src/"],
                    timeouts=TimeoutConfig(phase_seconds=77),
                )
            ]
        )
        self.adw_id = "run-123"
        self.session_dir = tmp_path / "session"
        self.context_handoff_dir = self.session_dir / "handoff"
        self.context_handoff_dir.mkdir(parents=True)
        self.repo_root = tmp_path
        self.agent_map = agent_map or {}
        self.tracer = FakeTracer()
        self.console = FakeConsole()
        self.tokens = 0
        self.cost = 0.0

    def add_usage(self, tokens: int, cost: float) -> None:
        self.tokens += tokens
        self.cost += cost

    def save_agent_map(self, agent: str, entry: dict[str, str]) -> None:
        self.agent_map[agent] = entry


def phase(*, retries: int = 0) -> Phase:
    return Phase(
        phase_id="run-123_01_build",
        adw_id="run-123",
        seq=1,
        params=PhaseParams(
            name="build",
            kind="agent",
            owner="builder",
            description="Build the requested feature and report the result.",
            retries=retries,
        ),
    )


def call(*, gates: list[Any] | None = None) -> AgentCall:
    return AgentCall(
        output_type=EnvelopeBase,
        prompt="add a health endpoint",
        gates=gates or [],
    )


def result(
    text: str,
    session_id: str,
    *,
    tokens: int = 10,
    runtime: RuntimeInfo | None = None,
) -> AgentResult:
    return AgentResult(
        text=text,
        session_id=session_id,
        usage=UsageBreakdown(total_tokens=tokens, total_cost=0.25),
        context_tokens=123,
        context_window=456,
        runtime=runtime
        or RuntimeInfo(
            sdk_version="1.0.13",
            runtime_version="1.2.3",
            protocol_version="3",
            cli_version="1.0.0",
        ),
    )


@pytest.fixture(autouse=True)
def permissions_are_stable(monkeypatch):
    monkeypatch.setattr(agents.permissions, "snapshot", lambda _run: {"baseline": True})
    monkeypatch.setattr(agents.permissions, "enforce", lambda *_args: [])


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _permission_run(tmp_path: Path) -> tuple[FakeRun, Path]:
    run = FakeRun(tmp_path)
    run.session_dir = tmp_path / "adws" / "adw_data" / "sessions" / run.adw_id
    run.context_handoff_dir = run.session_dir / "context_handoff"
    run.context_handoff_dir.mkdir(parents=True)
    protected = tmp_path / "protected.txt"
    protected.write_text("original\n")
    _run_git(tmp_path, "init", "-q")
    _run_git(tmp_path, "config", "user.email", "tests@example.invalid")
    _run_git(tmp_path, "config", "user.name", "SSSF tests")
    _run_git(tmp_path, "add", "protected.txt")
    _run_git(tmp_path, "commit", "-qm", "baseline")
    return run, protected


def _use_real_permission_enforcement(monkeypatch) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    def enforce(*args):
        calls.append(args)
        return REAL_PERMISSION_ENFORCE(*args)

    monkeypatch.setattr(agents.permissions, "snapshot", REAL_PERMISSION_SNAPSHOT)
    monkeypatch.setattr(agents.permissions, "enforce", enforce)
    return calls


def test_validate_calls_copilot_preflight_once(monkeypatch, tmp_path: Path):
    run = FakeRun(tmp_path)
    observed: list[SSSFConfig] = []

    monkeypatch.setattr(agents.agent_copilot, "validate", observed.append)

    agents.validate(run.cfg, ["builder"])

    assert observed == [run.cfg]


def test_execute_builds_copilot_request_from_agent_config(monkeypatch, tmp_path: Path):
    run = FakeRun(tmp_path)
    requests = []
    callbacks = []

    def fake_run(request, callback):
        requests.append(request)
        callbacks.append(callback)
        callback.on_event(AgentEvent(type="tool_call", payload={"label": "view: README"}))
        return result(
            '{"status": "success", "summary": "implemented", "artifacts": ["src/app.py"]}',
            request.session_id,
        )

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    envelope = agents.execute(run, phase(), call())

    request = requests[0]
    assert envelope.summary == "implemented"
    assert request.model == "gpt-5.4"
    assert request.reasoning_effort == "high"
    assert request.context_tier == "long_context"
    assert request.resume is False
    assert request.runtime_dir == str((run.session_dir / "builder" / "copilot").resolve())
    assert request.raw_output_path == str(
        (run.session_dir / "builder" / "raw_output.jsonl").resolve()
    )
    assert request.tools == ["view", "bash"]
    assert request.skill_directories == ["skills"]
    assert request.plugin_directories == ["plugins"]
    assert request.mcp_servers == {"zeta": {"type": "local"}, "alpha": {"type": "http"}}
    assert request.timeout_seconds == 77
    assert request.cwd == str(run.repo_root)
    assert callbacks[0].on_event is not None
    start = next(event for event in run.tracer.events if event.type == "agent_start")
    assert start.payload["coding_agent"] == "copilot"
    assert start.payload["mcp_servers"] == ["alpha", "zeta"]
    tool = next(event for event in run.tracer.events if event.type == "tool_call")
    assert tool.name == "view: README"
    assert tool.payload["agent"] == "builder"
    assert run.tracer.sessions == [{
        "agent": "builder",
        "coding_agent": "copilot",
        "session_id": request.session_id,
        "context_tokens": 123,
        "context_window": 456,
        "runtime": RuntimeInfo(
            sdk_version="1.0.13",
            runtime_version="1.2.3",
            protocol_version="3",
            cli_version="1.0.0",
        ),
    }]


def test_invalid_json_retries_same_session(monkeypatch, tmp_path: Path):
    run = FakeRun(tmp_path)
    requests = []

    def fake_run(request, _callbacks):
        requests.append(request)
        text = (
            "not-json"
            if len(requests) == 1
            else '{"status": "success", "summary": "repaired"}'
        )
        return result(text, request.session_id)

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    assert agents.execute(run, phase(), call()).summary == "repaired"

    assert [request.session_id for request in requests] == [
        requests[0].session_id,
        requests[0].session_id,
    ]
    assert [request.resume for request in requests] == [False, True]
    assert run.tracer.envelopes == [(False, 1), (True, 2)]
    assert run.tokens == 20


def test_gate_failure_retries_same_session(monkeypatch, tmp_path: Path):
    run = FakeRun(tmp_path)
    requests = []

    def fake_run(request, _callbacks):
        requests.append(request)
        return result('{"status": "success", "summary": "ready"}', request.session_id)

    gate_calls = 0

    def requires_second_answer(_envelope, _run):
        nonlocal gate_calls
        gate_calls += 1
        return ["missing test"] if gate_calls == 1 else []

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    envelope = agents.execute(run, phase(retries=1), call(gates=[requires_second_answer]))
    assert envelope.summary == "ready"

    assert [request.resume for request in requests] == [False, True]
    assert requests[0].session_id == requests[1].session_id
    assert "missing test" in requests[1].prompt
    assert run.tracer.gates == [("requires_second_answer", 1), ("requires_second_answer", 2)]


def test_permission_enforcement_runs_after_all_sends(monkeypatch, tmp_path: Path):
    run = FakeRun(tmp_path)
    requests = []
    enforcement_send_counts = []

    def fake_run(request, _callbacks):
        requests.append(request)
        text = "no JSON" if len(requests) == 1 else '{"status": "success"}'
        return result(text, request.session_id)

    def enforce(*_args):
        enforcement_send_counts.append(len(requests))
        return ["src/app.py"]

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)
    monkeypatch.setattr(agents.permissions, "enforce", enforce)

    agents.execute(run, phase(), call())

    assert enforcement_send_counts == [1, 2]
    assert any(event.name == "paths_touched" for event in run.tracer.events)


def test_success_enforces_once_without_a_second_exit_check(monkeypatch, tmp_path: Path):
    run = FakeRun(tmp_path)
    calls = []

    def enforce(*_args):
        calls.append(None)
        return []

    monkeypatch.setattr(
        agents.agent_copilot,
        "run",
        lambda request, _callbacks: result('{"status": "success"}', request.session_id),
    )
    monkeypatch.setattr(agents.permissions, "enforce", enforce)

    agents.execute(run, phase(), call())

    assert calls == [None]


def test_timeout_propagates_and_records_error(monkeypatch, tmp_path: Path):
    run = FakeRun(tmp_path)

    def fake_run(_request, _callbacks):
        raise TimeoutError("phase deadline exceeded")

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    with pytest.raises(TimeoutError, match="phase deadline exceeded"):
        agents.execute(run, phase(), call())

    error = next(event for event in run.tracer.events if event.type == "error")
    assert error.name == "builder"
    assert error.payload == {"agent": "builder", "error": "phase deadline exceeded"}


def test_timeout_write_is_rolled_back_and_permission_breach_is_authoritative(
    monkeypatch,
    tmp_path: Path,
):
    run, protected = _permission_run(tmp_path)
    enforcement_calls = _use_real_permission_enforcement(monkeypatch)

    def fake_run(_request, _callbacks):
        protected.write_text("unauthorized timeout write\n")
        raise TimeoutError("phase deadline exceeded")

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    with pytest.raises(permissions.PermissionBreach) as raised:
        agents.execute(run, phase(), call())

    assert protected.read_text() == "original\n"
    assert isinstance(raised.value.__cause__, TimeoutError)
    assert len(enforcement_calls) == 1
    permission_error = next(
        event for event in run.tracer.events if event.name == "permission_breach"
    )
    assert permission_error.payload["operation_error"] == "phase deadline exceeded"


def test_runtime_crash_write_is_rolled_back_and_permission_breach_is_authoritative(
    monkeypatch,
    tmp_path: Path,
):
    run, protected = _permission_run(tmp_path)
    enforcement_calls = _use_real_permission_enforcement(monkeypatch)

    def fake_run(_request, _callbacks):
        protected.write_text("unauthorized crash write\n")
        raise RuntimeError("Copilot runtime crashed")

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    with pytest.raises(permissions.PermissionBreach) as raised:
        agents.execute(run, phase(), call())

    assert protected.read_text() == "original\n"
    assert isinstance(raised.value.__cause__, RuntimeError)
    assert len(enforcement_calls) == 1


def test_invalid_response_write_blocks_its_correction_send(monkeypatch, tmp_path: Path):
    run, protected = _permission_run(tmp_path)
    _use_real_permission_enforcement(monkeypatch)
    requests = []

    def fake_run(request, _callbacks):
        requests.append(request)
        protected.write_text("unauthorized invalid response write\n")
        return result("not-json", request.session_id)

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    with pytest.raises(permissions.PermissionBreach):
        agents.execute(run, phase(), call())

    assert len(requests) == 1
    assert protected.read_text() == "original\n"


def test_parse_exhaustion_write_is_rolled_back_before_another_correction(
    monkeypatch,
    tmp_path: Path,
):
    run, protected = _permission_run(tmp_path)
    enforcement_calls = _use_real_permission_enforcement(monkeypatch)
    requests = []

    def fake_run(request, _callbacks):
        requests.append(request)
        if len(requests) == agents.JSON_FIX_ATTEMPTS + 1:
            protected.write_text("unauthorized invalid response write\n")
        return result("not-json", request.session_id)

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    with pytest.raises(permissions.PermissionBreach):
        agents.execute(run, phase(), call())

    assert len(requests) == agents.JSON_FIX_ATTEMPTS + 1
    assert protected.read_text() == "original\n"
    assert len(enforcement_calls) == agents.JSON_FIX_ATTEMPTS + 1


def test_gate_exhaustion_write_is_rolled_back_before_terminal_gate_failure(
    monkeypatch,
    tmp_path: Path,
):
    run, protected = _permission_run(tmp_path)
    enforcement_calls = _use_real_permission_enforcement(monkeypatch)
    requests = []

    def fake_run(request, _callbacks):
        requests.append(request)
        if len(requests) == 2:
            protected.write_text("unauthorized gate correction write\n")
        return result('{"status": "success"}', request.session_id)

    def always_fails(_envelope, _run):
        return ["required artifact is missing"]

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    with pytest.raises(permissions.PermissionBreach):
        agents.execute(run, phase(retries=1), call(gates=[always_fails]))

    assert len(requests) == 2
    assert protected.read_text() == "original\n"
    assert len(enforcement_calls) == 2


def test_runtime_versions_are_traced(monkeypatch, tmp_path: Path):
    run = FakeRun(tmp_path)
    runtime = RuntimeInfo(
        sdk_version="1.0.13",
        runtime_version="runtime-2.0",
        protocol_version="3",
        cli_version="1.5.0",
    )

    monkeypatch.setattr(
        agents.agent_copilot,
        "run",
        lambda request, _callbacks: result(
            '{"status": "success"}',
            request.session_id,
            runtime=runtime,
        ),
    )

    agents.execute(run, phase(), call())

    end = next(event for event in run.tracer.events if event.type == "agent_end")
    assert end.payload["sdk_version"] == "1.0.13"
    assert end.payload["runtime_version"] == "runtime-2.0"
    assert end.payload["protocol_version"] == "3"
    assert end.payload["cli_version"] == "1.5.0"


def test_existing_copilot_agent_map_resumes_first_send(monkeypatch, tmp_path: Path):
    run = FakeRun(
        tmp_path,
        agent_map={
            "builder": {
                "session_id": "persisted-session",
                "model": "gpt-5.4",
                "runtime": "copilot",
            }
        },
    )
    requests = []

    def fake_run(request, _callbacks):
        requests.append(request)
        return result('{"status": "success"}', request.session_id)

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    agents.execute(run, phase(), call())

    assert requests[0].session_id == "persisted-session"
    assert requests[0].resume is True


def test_pi_agent_map_entry_does_not_resume_in_copilot(monkeypatch, tmp_path: Path):
    run = FakeRun(
        tmp_path,
        agent_map={"builder": {"session_id": "pi-session", "model": "gpt-5.4", "runtime": "pi"}},
    )
    requests = []

    def fake_run(request, _callbacks):
        requests.append(request)
        return result('{"status": "success"}', request.session_id)

    monkeypatch.setattr(agents.agent_copilot, "run", fake_run)

    agents.execute(run, phase(), call())

    assert requests[0].session_id != "pi-session"
    assert requests[0].resume is False
