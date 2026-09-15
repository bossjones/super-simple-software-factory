"""Official SDK lifecycle adapter for SSSF Copilot agent calls."""

from __future__ import annotations

import asyncio
import fcntl
import importlib.metadata
import json
import os
import subprocess
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from copilot import CopilotClient, PermissionNoResult
from copilot.rpc import PermissionDecisionApproveOnce

from .copilot_events import CopilotEventNormalizer
from .data_types import (
    AgentCallbacks,
    AgentRequest,
    AgentResult,
    RuntimeInfo,
    SSSFConfig,
)
from .redaction import redact_text, sanitize_for_persistence

EXPECTED_SDK_VERSION = "1.0.13"
EXPECTED_PROTOCOL_VERSION = "3"
CLEANUP_TIMEOUT_SECONDS = 10.0
FORCE_STOP_TIMEOUT_SECONDS = 5.0


class EvidencePersistenceError(RuntimeError):
    """Required Copilot event evidence could not be persisted."""


class RuntimeCleanupError(RuntimeError):
    """The Copilot session or runtime could not be cleaned up safely."""


@dataclass
class _EvidenceState:
    signal: asyncio.Event = field(default_factory=asyncio.Event)
    stage: str = ""
    error: Exception | None = None

    def capture(self, stage: str, error: Exception) -> None:
        if self.error is None:
            self.stage = stage
            self.error = error
            self.signal.set()

    def raise_if_failed(self, cleanup_issues: list[str] | None = None) -> None:
        if self.error is None:
            return
        failure = EvidencePersistenceError(
            f"Copilot event evidence failed during {self.stage}: "
            f"{redact_text(str(self.error)) or type(self.error).__name__}"
        )
        _add_cleanup_notes(failure, cleanup_issues or [])
        raise failure from self.error


def validate(config: SSSFConfig) -> RuntimeInfo:
    """Verify the pinned SDK and managed runtime can serve SSSF calls."""
    installed = importlib.metadata.version("github-copilot-sdk")
    if installed != EXPECTED_SDK_VERSION:
        raise RuntimeError(
            f"github-copilot-sdk {installed} is installed; SSSF requires {EXPECTED_SDK_VERSION}"
        )
    return asyncio.run(_validate_runtime(config, installed))


async def _validate_runtime(config: SSSFConfig, sdk_version: str) -> RuntimeInfo:
    client = CopilotClient(
        mode="empty",
        base_directory=str(Path(config.defaults.data_dir) / "copilot-runtime"),
    )
    try:
        await client.start()
        status = await client.get_status()
        protocol_version = str(status.protocol_version)
        if protocol_version != EXPECTED_PROTOCOL_VERSION:
            raise RuntimeError(
                f"Copilot runtime protocol {status.protocol_version} is incompatible; "
                f"SSSF requires {EXPECTED_PROTOCOL_VERSION}"
            )
        runtime_info = RuntimeInfo(
            sdk_version=sdk_version,
            runtime_version=str(status.version),
            protocol_version=protocol_version,
            cli_version=_cli_version(),
        )
    except BaseException as error:
        _add_cleanup_notes(error, await _cleanup(client))
        raise
    else:
        cleanup_issues = await _cleanup(client)
        if cleanup_issues:
            raise RuntimeCleanupError("; ".join(cleanup_issues))
        return runtime_info


def run(request: AgentRequest, callbacks: AgentCallbacks) -> AgentResult:
    """Execute one prompt against a caller-owned Copilot session."""
    return asyncio.run(_run(request, callbacks))


async def _run(request: AgentRequest, callbacks: AgentCallbacks) -> AgentResult:
    descriptor, _lock_path = _acquire_session_lock(request)
    try:
        return await _run_locked(request, callbacks)
    finally:
        _release_session_lock(descriptor)


async def _run_locked(request: AgentRequest, callbacks: AgentCallbacks) -> AgentResult:
    client = CopilotClient(
        mode="empty",
        base_directory=request.runtime_dir,
        working_directory=request.cwd,
    )
    session: Any | None = None
    evidence = _EvidenceState()
    try:
        await client.start()
        status = await client.get_status()
        normalizer = CopilotEventNormalizer()
        active_session = await _create_or_resume(
            client,
            request,
            callbacks,
            normalizer,
            evidence,
        )
        session = active_session
        evidence.raise_if_failed()
        normalizer.final_text = ""
        try:
            await _send_with_evidence(
                active_session,
                request.prompt,
                request.timeout_seconds,
                evidence,
            )
        except TimeoutError as error:
            _add_cleanup_notes(error, await _abort(active_session))
            raise

        evidence.raise_if_failed()
        if not normalizer.final_text:
            raise RuntimeError("Copilot session completed without a parent assistant message")

        result = AgentResult(
            text=normalizer.final_text,
            session_id=str(active_session.session_id),
            usage=normalizer.usage,
            context_tokens=normalizer.context_tokens,
            context_window=normalizer.context_window,
            runtime=RuntimeInfo(
                sdk_version=importlib.metadata.version("github-copilot-sdk"),
                runtime_version=str(status.version),
                protocol_version=str(status.protocol_version),
                cli_version=_cli_version(),
            ),
        )
    except BaseException as error:
        _add_cleanup_notes(error, await _cleanup(client, session))
        raise
    else:
        cleanup_issues = await _cleanup(client, session)
        if cleanup_issues:
            raise RuntimeCleanupError("; ".join(cleanup_issues))
        return result


async def _create_or_resume(
    client: Any,
    request: AgentRequest,
    callbacks: AgentCallbacks,
    normalizer: CopilotEventNormalizer,
    evidence: _EvidenceState,
) -> Any:
    raw_path = Path(request.raw_output_path)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    def handle_event(event: Any) -> None:
        if evidence.error is not None:
            return
        stage = "event serialization"
        try:
            payload = sanitize_for_persistence(_event_payload(event))
            stage = "raw event persistence"
            _append_raw_event(raw_path, payload)
            stage = "event normalization"
            normalized_events = normalizer.observe(event)
            if callbacks.on_event is not None:
                stage = "normalized trace callback"
                for normalized in normalized_events:
                    callbacks.on_event(
                        normalized.model_copy(
                            update={"payload": sanitize_for_persistence(normalized.payload)}
                        )
                    )
        except Exception as error:
            evidence.capture(stage, error)
            if stage != "raw event persistence":
                _record_evidence_failure(raw_path, stage, error)

    options = {
        "model": request.model,
        "reasoning_effort": request.reasoning_effort,
        "context_tier": request.context_tier,
        "available_tools": request.tools,
        "system_message": {"mode": "append", "content": request.system_prompt},
        "working_directory": request.cwd,
        "streaming": True,
        "mcp_servers": request.mcp_servers,
        "enable_skills": bool(request.skill_directories),
        "skill_directories": request.skill_directories,
        "plugin_directories": request.plugin_directories,
        "on_permission_request": _approve_permission_once,
        "on_event": handle_event,
    }
    if request.resume:
        session = await client.resume_session(request.session_id, **options)
    else:
        session = await client.create_session(session_id=request.session_id, **options)
    if session is None:
        operation = "resume" if request.resume else "create"
        raise RuntimeError(f"Copilot session {operation} returned no session")
    return session


def _acquire_session_lock(request: AgentRequest) -> tuple[int, Path]:
    lock_path = Path(request.runtime_dir) / "locks" / f"{request.session_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(descriptor)
        raise RuntimeError(
            f"Copilot session {request.session_id!r} is already active; "
            "concurrent mutation is not allowed"
        ) from error
    os.ftruncate(descriptor, 0)
    os.write(descriptor, f"pid={os.getpid()}\n".encode())
    return descriptor, lock_path


def _release_session_lock(descriptor: int) -> None:
    try:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _consume_task_result(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        return
    try:
        task.exception()
    except BaseException:
        pass


async def _bounded_operation(
    name: str,
    operation: Callable[[], Awaitable[Any]],
    timeout_seconds: float,
) -> str | None:
    task = asyncio.ensure_future(operation())
    done, _pending = await asyncio.wait({task}, timeout=timeout_seconds)
    if task not in done:
        task.cancel()
        task.add_done_callback(_consume_task_result)
        return f"{name} timed out after {timeout_seconds:g}s"
    try:
        task.result()
    except BaseException as error:
        return f"{name} failed: {redact_text(str(error)) or type(error).__name__}"
    return None


async def _abort(session: Any) -> list[str]:
    issue = await _bounded_operation(
        "session.abort",
        session.abort,
        CLEANUP_TIMEOUT_SECONDS,
    )
    return [issue] if issue else []


async def _cleanup(client: Any, session: Any | None = None) -> list[str]:
    issues: list[str] = []
    if session is not None:
        issue = await _bounded_operation(
            "session.disconnect",
            session.disconnect,
            CLEANUP_TIMEOUT_SECONDS,
        )
        if issue:
            issues.append(issue)

    stop_issue = await _bounded_operation(
        "client.stop",
        client.stop,
        CLEANUP_TIMEOUT_SECONDS,
    )
    if stop_issue:
        issues.append(stop_issue)
        force_stop: Any = getattr(client, "force_stop", None)
        if callable(force_stop):
            force_operation = cast(Callable[[], Awaitable[Any]], force_stop)
            force_issue = await _bounded_operation(
                "client.force_stop",
                force_operation,
                FORCE_STOP_TIMEOUT_SECONDS,
            )
            if force_issue:
                issues.append(force_issue)
        else:
            issues.append("client.force_stop is unavailable")
    return issues


async def _send_with_evidence(
    session: Any,
    prompt: str,
    timeout_seconds: int,
    evidence: _EvidenceState,
) -> None:
    evidence.raise_if_failed()
    send_task = asyncio.create_task(session.send_and_wait(prompt, timeout=timeout_seconds))
    failure_task = asyncio.create_task(evidence.signal.wait())
    try:
        await asyncio.wait({send_task, failure_task}, return_when=asyncio.FIRST_COMPLETED)
        if evidence.error is not None:
            abort_issues = await _abort(session)
            if not send_task.done():
                send_task.cancel()
                send_task.add_done_callback(_consume_task_result)
            evidence.raise_if_failed(abort_issues)
        await send_task
        evidence.raise_if_failed()
    finally:
        if not failure_task.done():
            failure_task.cancel()
            failure_task.add_done_callback(_consume_task_result)


def _event_payload(event: Any) -> Mapping[str, Any]:
    to_dict = getattr(event, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    else:
        model_dump = getattr(event, "model_dump", None)
        payload = model_dump(mode="json") if callable(model_dump) else vars(event)
    if not isinstance(payload, Mapping):
        raise TypeError(
            f"Copilot event serializer returned {type(payload).__name__}, not a mapping"
        )
    return payload


def _append_raw_event(raw_path: Path, payload: Any) -> None:
    with raw_path.open("a", encoding="utf-8") as raw:
        raw.write(json.dumps(payload, default=str) + "\n")


def _record_evidence_failure(raw_path: Path, stage: str, error: Exception) -> None:
    try:
        _append_raw_event(
            raw_path,
            {
                "type": "sssf.evidence_failure",
                "data": {
                    "stage": stage,
                    "error_type": type(error).__name__,
                    "message": redact_text(str(error)),
                },
            },
        )
    except Exception:
        pass


def _add_cleanup_notes(error: BaseException, issues: list[str]) -> None:
    for issue in issues:
        error.add_note(f"Copilot cleanup: {issue}")


def _approve_permission_once(request: Any, _invocation: Any) -> Any:
    if getattr(request, "managed_approval_required", False):
        return PermissionNoResult()
    return PermissionDecisionApproveOnce()


def _cli_version() -> str:
    """Capture CLI version only as diagnostic metadata."""
    try:
        result = subprocess.run(
            ["copilot", "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""
