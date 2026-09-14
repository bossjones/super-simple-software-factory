"""Official SDK lifecycle adapter for SSSF Copilot agent calls."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
import subprocess
from pathlib import Path
from typing import Any

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

EXPECTED_SDK_VERSION = "1.0.13"
EXPECTED_PROTOCOL_VERSION = "3"


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
    except BaseException:
        await _cleanup_after_failure(client)
        raise
    else:
        await client.stop()
        return runtime_info


def run(request: AgentRequest, callbacks: AgentCallbacks) -> AgentResult:
    """Execute one prompt against a caller-owned Copilot session."""
    return asyncio.run(_run(request, callbacks))


async def _run(request: AgentRequest, callbacks: AgentCallbacks) -> AgentResult:
    descriptor, lock_path = _acquire_session_lock(request)
    try:
        return await _run_locked(request, callbacks)
    finally:
        try:
            os.close(descriptor)
        finally:
            lock_path.unlink(missing_ok=True)


async def _run_locked(request: AgentRequest, callbacks: AgentCallbacks) -> AgentResult:
    client = CopilotClient(
        mode="empty",
        base_directory=request.runtime_dir,
        working_directory=request.cwd,
    )
    session: Any | None = None
    try:
        await client.start()
        status = await client.get_status()
        normalizer = CopilotEventNormalizer()
        active_session = await _create_or_resume(client, request, callbacks, normalizer)
        session = active_session
        normalizer.final_text = ""
        try:
            await active_session.send_and_wait(
                request.prompt,
                timeout=request.timeout_seconds,
            )
        except TimeoutError:
            await active_session.abort()
            raise

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
    except BaseException:
        await _cleanup_after_failure(client, session)
        raise
    else:
        await _cleanup(client, session)
        return result


async def _create_or_resume(
    client: Any,
    request: AgentRequest,
    callbacks: AgentCallbacks,
    normalizer: CopilotEventNormalizer,
) -> Any:
    raw_path = Path(request.raw_output_path)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    def handle_event(event: Any) -> None:
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else vars(event)
        with raw_path.open("a", encoding="utf-8") as raw:
            raw.write(json.dumps(payload, default=str) + "\n")
        for normalized in normalizer.observe(event):
            if callbacks.on_event is not None:
                callbacks.on_event(normalized)

    options = {
        "model": request.model,
        "reasoning_effort": request.reasoning_effort,
        "context_tier": request.context_tier,
        "available_tools": request.tools,
        "system_message": {"mode": "append", "content": request.system_prompt},
        "working_directory": request.cwd,
        "streaming": True,
        "mcp_servers": request.mcp_servers,
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
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(
            f"Copilot session {request.session_id!r} is already active; "
            "concurrent mutation is not allowed"
        ) from error
    return descriptor, lock_path


async def _cleanup(client: Any, session: Any | None = None) -> None:
    try:
        if session is not None:
            await session.disconnect()
    finally:
        await client.stop()


async def _cleanup_after_failure(client: Any, session: Any | None = None) -> None:
    """Attempt all cleanup without replacing the operational failure."""
    try:
        await _cleanup(client, session)
    except BaseException:
        pass


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
