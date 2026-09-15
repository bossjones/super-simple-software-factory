from __future__ import annotations

import asyncio
import importlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from adw_modules.data_types import (
    AgentCallbacks,
    AgentEvent,
    AgentRequest,
    AgentResult,
    ConfigDefaults,
    EventRecord,
    SSSFConfig,
    UsageBreakdown,
)
from adw_modules.tracer import Tracer
from copilot.session_events import SessionEvent


class FakeNormalizer:
    def __init__(self) -> None:
        self.final_text = ""
        self.usage = UsageBreakdown()
        self.context_tokens = 0
        self.context_window = 0

    def observe(self, event: Any) -> list[AgentEvent]:
        event_type = getattr(event.type, "value", event.type)
        if event_type == "assistant.message" and getattr(event, "agent_id", None) is None:
            self.final_text = getattr(getattr(event, "data", None), "content", "") or ""
        return [AgentEvent(type="handoff", payload={"event": event_type})]


class FakeSession:
    def __init__(
        self,
        session_id: str,
        events: list[Any],
        result_text: str = "{}",
        send_error: Exception | None = None,
        disconnect_error: Exception | None = None,
        startup_events: list[Any] | None = None,
        abort_error: Exception | None = None,
        hang_abort: bool = False,
        hang_disconnect: bool = False,
    ) -> None:
        self.session_id = session_id
        self.events = events
        self.result_text = result_text
        self.send_error = send_error
        self.disconnect_error = disconnect_error
        self.startup_events = startup_events or []
        self.abort_error = abort_error
        self.hang_abort = hang_abort
        self.hang_disconnect = hang_disconnect
        self.handlers: list[Any] = []
        self.aborted = False
        self.disconnected = False
        self.lifecycle: list[str] = []

    def on(self, handler: Any) -> Any:
        self.handlers.append(handler)
        return lambda: self.handlers.remove(handler)

    async def send_and_wait(self, prompt: str, timeout: float | None = None) -> Any:
        self.lifecycle.append("send")
        for event in self.events:
            for handler in list(self.handlers):
                handler(event)
        if self.send_error is not None:
            raise self.send_error
        return SimpleNamespace(data=SimpleNamespace(content=self.result_text))

    async def abort(self) -> None:
        self.aborted = True
        self.lifecycle.append("abort")
        if self.hang_abort:
            await asyncio.Event().wait()
        if self.abort_error is not None:
            raise self.abort_error

    async def disconnect(self) -> None:
        self.disconnected = True
        self.lifecycle.append("disconnect")
        if self.hang_disconnect:
            await asyncio.Event().wait()
        if self.disconnect_error is not None:
            raise self.disconnect_error


class FakeClient:
    def __init__(
        self,
        *,
        create_session: FakeSession | None = None,
        resume_session: FakeSession | None = None,
        start_error: Exception | None = None,
        stop_error: Exception | None = None,
        hang_stop: bool = False,
        force_stop_error: Exception | None = None,
        hang_force_stop: bool = False,
        **kwargs: Any,
    ) -> None:
        self.created = create_session
        self.resumed = resume_session
        self.kwargs = kwargs
        self.start_error = start_error
        self.stop_error = stop_error
        self.hang_stop = hang_stop
        self.force_stop_error = force_stop_error
        self.hang_force_stop = hang_force_stop
        self.started = False
        self.stopped = False
        self.force_stopped = False
        self.create_kwargs: dict[str, Any] = {}
        self.resume_kwargs: dict[str, Any] = {}
        self.resume_id = ""

    async def start(self) -> None:
        self.started = True
        if self.start_error is not None:
            raise self.start_error

    async def get_status(self) -> Any:
        return SimpleNamespace(version="runtime-1", protocol_version="3")

    async def create_session(self, **kwargs: Any) -> FakeSession | None:
        self.create_kwargs = kwargs
        session = self.created
        if session is not None:
            for event in session.startup_events:
                kwargs["on_event"](event)
            session.handlers.append(kwargs["on_event"])
        return session

    async def resume_session(self, session_id: str, **kwargs: Any) -> FakeSession | None:
        self.resume_id = session_id
        self.resume_kwargs = kwargs
        session = self.resumed
        if session is not None:
            for event in session.startup_events:
                kwargs["on_event"](event)
            session.handlers.append(kwargs["on_event"])
        return session

    async def stop(self) -> None:
        self.stopped = True
        if self.hang_stop:
            await asyncio.Event().wait()
        if self.stop_error is not None:
            raise self.stop_error

    async def force_stop(self) -> None:
        self.force_stopped = True
        if self.hang_force_stop:
            await asyncio.Event().wait()
        if self.force_stop_error is not None:
            raise self.force_stop_error


def request(tmp_path: Path, *, resume: bool = False) -> AgentRequest:
    return AgentRequest(
        prompt="Return an envelope.",
        system_prompt="Be precise.",
        model="gpt-5.4",
        reasoning_effort="high",
        context_tier="default",
        session_id="session-123",
        resume=resume,
        runtime_dir=str(tmp_path / "runtime"),
        raw_output_path=str(tmp_path / "raw" / "events.jsonl"),
        tools=["view"],
        skill_directories=["skills"],
        plugin_directories=["plugins"],
        mcp_servers={"local": {"type": "local"}},
        timeout_seconds=42,
        cwd=str(tmp_path),
    )


def load_runtime(monkeypatch) -> Any:
    events: Any = ModuleType("adw_modules.copilot_events")
    events.CopilotEventNormalizer = FakeNormalizer
    monkeypatch.setitem(sys.modules, "adw_modules.copilot_events", events)
    monkeypatch.delitem(sys.modules, "adw_modules.agent_copilot", raising=False)
    return importlib.import_module("adw_modules.agent_copilot")


def install_client(monkeypatch, runtime: Any, client: FakeClient) -> None:
    def client_constructor(**kwargs: Any) -> FakeClient:
        client.kwargs = kwargs
        return client

    monkeypatch.setattr(runtime, "CopilotClient", client_constructor)


def test_create_uses_empty_mode_explicit_tools_and_caller_session_id(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    event = SimpleNamespace(type="assistant.message", data=SimpleNamespace(content="final"))
    session = FakeSession("session-123", [event])
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)
    captured: list[AgentEvent] = []

    result = runtime.run(request(tmp_path), AgentCallbacks(on_event=captured.append))

    assert isinstance(result, AgentResult)
    assert result.text == "final"
    assert result.session_id == "session-123"
    assert client.kwargs["mode"] == "empty"
    assert client.kwargs["base_directory"] == request(tmp_path).runtime_dir
    assert client.create_kwargs["session_id"] == request(tmp_path).session_id
    assert client.create_kwargs["available_tools"] == request(tmp_path).tools
    assert client.create_kwargs["enable_skills"] is True
    assert client.create_kwargs["skill_directories"] == ["skills"]
    assert client.create_kwargs["plugin_directories"] == ["plugins"]
    assert client.create_kwargs["reasoning_effort"] == request(tmp_path).reasoning_effort
    assert client.create_kwargs["working_directory"] == request(tmp_path).cwd
    assert client.started is True
    assert client.stopped is True
    assert session.disconnected is True
    assert captured == [AgentEvent(type="handoff", payload={"event": "assistant.message"})]
    raw_lines = (tmp_path / "raw" / "events.jsonl").read_text().splitlines()
    assert len(raw_lines) == 1
    assert json.loads(raw_lines[0])["type"] == "assistant.message"


def test_resume_reuses_session_id(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    startup_event = SimpleNamespace(
        id="startup-replay",
        type="assistant.message",
        agent_id=None,
        data=SimpleNamespace(content="previous turn"),
    )
    current_event = SimpleNamespace(
        id="current-turn",
        type="assistant.message",
        agent_id=None,
        data=SimpleNamespace(content="current turn"),
    )
    session = FakeSession("session-123", [current_event], startup_events=[startup_event])
    client = FakeClient(
        create_session=FakeSession("replacement", []),
        resume_session=session,
    )
    install_client(monkeypatch, runtime, client)

    events: list[AgentEvent] = []
    result = runtime.run(request(tmp_path, resume=True), AgentCallbacks(on_event=events.append))

    assert result.text == "current turn"
    assert result.session_id == "session-123"
    assert client.resume_id == "session-123"
    assert client.create_kwargs == {}
    assert client.resume_kwargs["available_tools"] == ["view"]
    assert client.resume_kwargs["enable_skills"] is True
    assert client.resume_kwargs["skill_directories"] == ["skills"]
    assert client.resume_kwargs["plugin_directories"] == ["plugins"]
    assert events == [
        AgentEvent(type="handoff", payload={"event": "assistant.message"}),
        AgentEvent(type="handoff", payload={"event": "assistant.message"}),
    ]
    raw_events = [
        json.loads(line)
        for line in Path(request(tmp_path, resume=True).raw_output_path).read_text().splitlines()
    ]
    assert [event["id"] for event in raw_events] == ["startup-replay", "current-turn"]


def test_timeout_calls_abort_before_disconnect(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    session = FakeSession("session-123", [], send_error=TimeoutError("deadline"))
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)

    with pytest.raises(TimeoutError, match="deadline"):
        runtime.run(request(tmp_path), AgentCallbacks())

    assert session.aborted is True
    assert session.lifecycle == ["send", "abort", "disconnect"]
    assert client.stopped is True
    assert (tmp_path / "runtime" / "locks" / "session-123.lock").exists()


def test_events_are_subscribed_before_send(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    event = SimpleNamespace(
        id="startup-event",
        type="assistant.message",
        agent_id=None,
        data=SimpleNamespace(content="before send"),
    )
    current_event = SimpleNamespace(
        id="sent-event",
        type="assistant.message",
        agent_id=None,
        data=SimpleNamespace(content="from current send"),
    )
    session = FakeSession("session-123", [current_event], startup_events=[event])
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)
    events: list[AgentEvent] = []

    result = runtime.run(request(tmp_path), AgentCallbacks(on_event=events.append))

    assert session.lifecycle[0] == "send"
    assert result.text == "from current send"
    assert events == [
        AgentEvent(type="handoff", payload={"event": "assistant.message"}),
        AgentEvent(type="handoff", payload={"event": "assistant.message"}),
    ]
    raw_lines = (tmp_path / "raw" / "events.jsonl").read_text().splitlines()
    assert [json.loads(line)["id"] for line in raw_lines] == ["startup-event", "sent-event"]


def test_raw_and_normalized_event_persistence_redacts_credentials(
    monkeypatch,
    tmp_path: Path,
):
    runtime = load_runtime(monkeypatch)
    configured_token = "gho_configured_secret_value"
    nested_secret = "nested-client-secret"
    bearer_secret = "unconfigured-bearer-secret"
    monkeypatch.setenv("GH_TOKEN", configured_token)

    class SecretNormalizer(FakeNormalizer):
        def observe(self, event: Any) -> list[AgentEvent]:
            if event.type == "tool.execution_complete":
                return [
                    AgentEvent(
                        type="tool_call",
                        payload={
                            "tool": "view",
                            "args": event.data.arguments,
                            "result_snippet": event.data.result,
                        },
                    )
                ]
            return super().observe(event)

    monkeypatch.setattr(runtime, "CopilotEventNormalizer", SecretNormalizer)
    secret_event = SimpleNamespace(
        id="secret-event",
        type="tool.execution_complete",
        agent_id=None,
        data=SimpleNamespace(
            arguments={
                "path": "README.md",
                "authorization": f"Bearer {configured_token}",
                "nested": {
                    "clientSecret": nested_secret,
                    "message": f"token={configured_token}",
                },
            },
            result=f"Authorization: Bearer {bearer_secret}",
        ),
    )
    final_event = SimpleNamespace(
        id="final-event",
        type="assistant.message",
        agent_id=None,
        data=SimpleNamespace(content='{"status":"success"}'),
    )
    session = FakeSession("session-123", [secret_event, final_event])
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)

    tracer = Tracer(tmp_path / "trace" / "sssf.db", tmp_path / "trace" / "events.jsonl")

    def persist(event: AgentEvent) -> None:
        tracer.event(
            EventRecord(
                adw_id="run-1",
                phase_id="phase-1",
                type=event.type,
                payload=event.payload,
            )
        )

    runtime.run(request(tmp_path), AgentCallbacks(on_event=persist))

    raw_text = (tmp_path / "raw" / "events.jsonl").read_text()
    normalized_jsonl = (tmp_path / "trace" / "events.jsonl").read_text()
    sqlite_payload = tracer.conn.execute(
        "SELECT payload_json FROM events WHERE type='tool_call'"
    ).fetchone()[0]
    persisted = "\n".join((raw_text, normalized_jsonl, sqlite_payload))
    assert configured_token not in persisted
    assert nested_secret not in persisted
    assert bearer_secret not in persisted
    assert "README.md" in persisted
    assert "[REDACTED]" in persisted


def test_password_style_envelope_is_not_redacted_before_parsing(
    monkeypatch,
    tmp_path: Path,
):
    runtime = load_runtime(monkeypatch)
    envelope = json.dumps(
        {
            "status": "success",
            "summary": "Keep password=hunter2 as semantic output",
            "files_changed": [],
            "tests": [],
            "notes_for_next_agent": "credential=example-value",
            "failure": None,
            "metadata": {},
        }
    )
    event = SimpleNamespace(
        type="assistant.message",
        data=SimpleNamespace(content=envelope),
    )
    client = FakeClient(create_session=FakeSession("session-123", [event]))
    install_client(monkeypatch, runtime, client)

    result = runtime.run(request(tmp_path), AgentCallbacks())

    assert result.text == envelope
    assert json.loads(result.text)["summary"] == ("Keep password=hunter2 as semantic output")
    assert "hunter2" not in (tmp_path / "raw" / "events.jsonl").read_text()


def test_raw_persistence_uses_canonical_session_event_to_dict(
    monkeypatch,
    tmp_path: Path,
):
    runtime = load_runtime(monkeypatch)
    timestamp = datetime(2026, 9, 14, 12, 34, 56, tzinfo=UTC)
    message_id = "11111111-1111-1111-1111-111111111111"
    parent_id = "22222222-2222-2222-2222-222222222222"
    event = SessionEvent.from_dict(
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "type": "assistant.message",
            "timestamp": timestamp.isoformat(),
            "parentId": parent_id,
            "data": {"content": "final", "messageId": message_id},
        }
    )
    client = FakeClient(create_session=FakeSession("session-123", [event]))
    install_client(monkeypatch, runtime, client)

    runtime.run(request(tmp_path), AgentCallbacks())

    raw_event = json.loads((tmp_path / "raw" / "events.jsonl").read_text())
    assert raw_event["id"] == "33333333-3333-3333-3333-333333333333"
    assert raw_event["parentId"] == parent_id
    assert raw_event["timestamp"] == timestamp.isoformat()
    assert raw_event["data"]["messageId"] == message_id
    assert raw_event["type"] == "assistant.message"


def test_send_callback_failure_is_recorded_and_surfaced(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    event = SimpleNamespace(
        type="assistant.message",
        data=SimpleNamespace(content="final"),
    )
    client = FakeClient(create_session=FakeSession("session-123", [event]))
    install_client(monkeypatch, runtime, client)

    def fail_callback(_event: AgentEvent) -> None:
        raise RuntimeError("callback exploded")

    with pytest.raises(runtime.EvidencePersistenceError, match="callback"):
        runtime.run(request(tmp_path), AgentCallbacks(on_event=fail_callback))

    raw_events = [
        json.loads(line) for line in (tmp_path / "raw" / "events.jsonl").read_text().splitlines()
    ]
    assert raw_events[-1]["type"] == "sssf.evidence_failure"
    assert "callback exploded" in raw_events[-1]["data"]["message"]


def test_initialization_raw_failure_is_surfaced_when_sdk_swallows_callback_errors(
    monkeypatch,
    tmp_path: Path,
):
    runtime = load_runtime(monkeypatch)
    startup_event = SimpleNamespace(
        type="assistant.message",
        data=SimpleNamespace(content="replayed"),
    )
    session = FakeSession("session-123", [], startup_events=[startup_event])
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)
    raw_path = tmp_path / "raw" / "events.jsonl"
    raw_path.mkdir(parents=True)

    with pytest.raises(runtime.EvidencePersistenceError, match="raw event persistence"):
        runtime.run(
            request(tmp_path).model_copy(update={"raw_output_path": str(raw_path)}),
            AgentCallbacks(),
        )

    assert session.disconnected is True
    assert client.stopped is True


def test_permission_callback_only_approves_ordinary_requests(monkeypatch):
    runtime = load_runtime(monkeypatch)

    managed = runtime._approve_permission_once(
        SimpleNamespace(managed_approval_required=True),
        {},
    )
    ordinary = runtime._approve_permission_once(
        SimpleNamespace(managed_approval_required=False),
        {},
    )

    assert isinstance(managed, runtime.PermissionNoResult)
    assert isinstance(ordinary, runtime.PermissionDecisionApproveOnce)


def test_runtime_error_is_not_converted_to_success(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    session = FakeSession("session-123", [], send_error=RuntimeError("runtime crashed"))
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)

    with pytest.raises(RuntimeError, match="runtime crashed"):
        runtime.run(request(tmp_path), AgentCallbacks())

    assert session.aborted is False


def test_disconnect_and_client_stop_run_on_failure(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    session = FakeSession("session-123", [], send_error=RuntimeError("runtime crashed"))
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)

    with pytest.raises(RuntimeError):
        runtime.run(request(tmp_path), AgentCallbacks())

    assert session.disconnected is True
    assert client.stopped is True


def test_client_stop_runs_when_disconnect_fails(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    session = FakeSession(
        "session-123",
        [SimpleNamespace(type="assistant.message", data=SimpleNamespace(content="parent"))],
        disconnect_error=RuntimeError("disconnect failed"),
    )
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)

    with pytest.raises(RuntimeError, match="disconnect failed"):
        runtime.run(request(tmp_path), AgentCallbacks())

    assert session.disconnected is True
    assert client.stopped is True
    assert client.force_stopped is False


def test_stop_failure_uses_public_force_stop(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    session = FakeSession(
        "session-123",
        [SimpleNamespace(type="assistant.message", data=SimpleNamespace(content="parent"))],
    )
    client = FakeClient(
        create_session=session,
        stop_error=RuntimeError("stop failed"),
    )
    install_client(monkeypatch, runtime, client)

    with pytest.raises(runtime.RuntimeCleanupError, match="stop failed"):
        runtime.run(request(tmp_path), AgentCallbacks())

    assert client.force_stopped is True


def test_cleanup_timeouts_preserve_original_send_timeout(
    monkeypatch,
    tmp_path: Path,
):
    runtime = load_runtime(monkeypatch)
    monkeypatch.setattr(runtime, "CLEANUP_TIMEOUT_SECONDS", 0.01)
    original = TimeoutError("model timed out")
    session = FakeSession(
        "session-123",
        [],
        send_error=original,
        hang_abort=True,
        hang_disconnect=True,
    )
    client = FakeClient(create_session=session, hang_stop=True)
    install_client(monkeypatch, runtime, client)

    with pytest.raises(TimeoutError) as raised:
        runtime.run(request(tmp_path), AgentCallbacks())

    assert raised.value is original
    assert client.force_stopped is True
    notes = "\n".join(getattr(raised.value, "__notes__", []))
    assert "session.abort timed out" in notes
    assert "session.disconnect timed out" in notes
    assert "client.stop timed out" in notes


def test_runtime_does_not_access_private_cli_process(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    session = FakeSession(
        "session-123",
        [SimpleNamespace(type="assistant.message", data=SimpleNamespace(content="parent"))],
    )

    class PrivateProcessGuardClient(FakeClient):
        @property
        def _cli_process(self) -> None:
            raise AssertionError("runtime accessed private SDK state")

    client = PrivateProcessGuardClient(create_session=session)
    install_client(monkeypatch, runtime, client)
    result = runtime.run(request(tmp_path), AgentCallbacks())

    assert result.runtime is not None
    assert result.runtime.runtime_version == "runtime-1"


def test_active_session_lock_rejects_concurrent_mutation(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    client = FakeClient(create_session=FakeSession("session-123", []))
    install_client(monkeypatch, runtime, client)
    descriptor, lock_path = runtime._acquire_session_lock(request(tmp_path))
    try:
        with pytest.raises(RuntimeError, match="already active"):
            runtime.run(request(tmp_path), AgentCallbacks())
        assert client.started is False
    finally:
        runtime._release_session_lock(descriptor)

    assert lock_path.exists()


def test_session_lock_is_released_by_kernel_after_process_exit(
    monkeypatch,
    tmp_path: Path,
    repo_root: Path,
):
    runtime = load_runtime(monkeypatch)
    child = """
import os
import sys
from adw_modules.agent_copilot import _acquire_session_lock
from adw_modules.data_types import AgentRequest

request = AgentRequest.model_validate_json(sys.argv[1])
_acquire_session_lock(request)
os._exit(0)
"""
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = str(repo_root / "skills/sssf/templates/adws")
    completed = subprocess.run(
        [sys.executable, "-c", child, request(tmp_path).model_dump_json()],
        check=False,
        env=child_env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    descriptor, lock_path = runtime._acquire_session_lock(request(tmp_path))
    runtime._release_session_lock(descriptor)

    assert lock_path.exists()


def test_resume_failure_does_not_create_a_replacement_session(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    client = FakeClient(
        create_session=FakeSession("replacement", []),
        resume_session=None,
    )
    install_client(monkeypatch, runtime, client)

    with pytest.raises(RuntimeError, match="resume returned no session"):
        runtime.run(request(tmp_path, resume=True), AgentCallbacks())

    assert client.resume_id == "session-123"
    assert client.create_kwargs == {}
    assert client.stopped is True


def test_result_contains_normalized_usage_and_runtime_metadata(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)

    class UsageNormalizer(FakeNormalizer):
        def __init__(self) -> None:
            super().__init__()
            self.usage = UsageBreakdown(input_tokens=11, output_tokens=7, total_tokens=18)
            self.context_tokens = 18
            self.context_window = 128_000

    monkeypatch.setattr(runtime, "CopilotEventNormalizer", UsageNormalizer)
    monkeypatch.setattr(runtime, "_cli_version", lambda: "copilot 1.2.3")
    session = FakeSession(
        "session-123",
        [SimpleNamespace(type="assistant.message", data=SimpleNamespace(content="{}"))],
    )
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)

    result = runtime.run(request(tmp_path), AgentCallbacks())

    assert result.text == "{}"
    assert result.usage.input_tokens == 11
    assert result.context_tokens == 18
    assert result.context_window == 128_000
    assert result.runtime is not None
    assert result.runtime.sdk_version == "1.0.13"
    assert result.runtime.runtime_version == "runtime-1"
    assert result.runtime.protocol_version == "3"
    assert result.runtime.cli_version == "copilot 1.2.3"


def test_validate_starts_checks_status_and_stops(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    client = FakeClient()
    install_client(monkeypatch, runtime, client)
    monkeypatch.setattr(runtime.importlib.metadata, "version", lambda _: "1.0.13")
    monkeypatch.setattr(runtime, "_cli_version", lambda: "copilot 1.2.3")

    info = runtime.validate(SSSFConfig(defaults=ConfigDefaults(data_dir=str(tmp_path / "data"))))

    assert client.kwargs == {
        "mode": "empty",
        "base_directory": str(tmp_path / "data" / "copilot-runtime"),
    }
    assert client.started is True
    assert client.stopped is True
    assert info.protocol_version == "3"


def test_subagent_only_message_is_not_used_as_final_text(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    session = FakeSession(
        "session-123",
        [
            SimpleNamespace(
                type="assistant.message",
                agent_id="subagent-1",
                data=SimpleNamespace(content='{"status": "success"}'),
            )
        ],
        result_text='{"status": "success"}',
    )
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)

    with pytest.raises(RuntimeError, match="parent assistant message"):
        runtime.run(request(tmp_path), AgentCallbacks())

    assert session.disconnected is True
    assert client.stopped is True


def test_startup_replay_does_not_satisfy_current_turn(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    startup_event = SimpleNamespace(
        id="startup-replay",
        type="assistant.message",
        agent_id=None,
        data=SimpleNamespace(content="previous turn"),
    )
    session = FakeSession("session-123", [], startup_events=[startup_event])
    client = FakeClient(create_session=session)
    install_client(monkeypatch, runtime, client)
    events: list[AgentEvent] = []

    with pytest.raises(RuntimeError, match="parent assistant message"):
        runtime.run(request(tmp_path), AgentCallbacks(on_event=events.append))

    assert events == [AgentEvent(type="handoff", payload={"event": "assistant.message"})]
    raw_events = [
        json.loads(line) for line in (tmp_path / "raw" / "events.jsonl").read_text().splitlines()
    ]
    assert [event["id"] for event in raw_events] == ["startup-replay"]
    assert session.disconnected is True
    assert client.stopped is True


def test_run_stops_partially_started_client_and_preserves_start_error(monkeypatch, tmp_path: Path):
    runtime = load_runtime(monkeypatch)
    client = FakeClient(
        start_error=RuntimeError("start failed"),
        stop_error=RuntimeError("stop failed"),
    )
    install_client(monkeypatch, runtime, client)

    with pytest.raises(RuntimeError, match="start failed"):
        runtime.run(request(tmp_path), AgentCallbacks())

    assert client.started is True
    assert client.stopped is True
    assert (tmp_path / "runtime" / "locks" / "session-123.lock").exists()


def test_validate_stops_partially_started_client_and_preserves_start_error(
    monkeypatch, tmp_path: Path
):
    runtime = load_runtime(monkeypatch)
    client = FakeClient(
        start_error=RuntimeError("start failed"),
        stop_error=RuntimeError("stop failed"),
    )
    install_client(monkeypatch, runtime, client)
    monkeypatch.setattr(runtime.importlib.metadata, "version", lambda _: "1.0.13")

    with pytest.raises(RuntimeError, match="start failed"):
        runtime.validate(SSSFConfig(defaults=ConfigDefaults(data_dir=str(tmp_path / "data"))))

    assert client.started is True
    assert client.stopped is True
