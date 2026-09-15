"""Normalize public Copilot SDK session events for the SSSF control plane."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any

from .data_types import AgentEvent, UsageBreakdown
from .redaction import REDACTED, is_sensitive_key, redact_text

RESULT_SNIPPET_CHARS = 20_000
ARG_VALUE_CHARS = 20_000


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _safe_value(
    value: Any,
    limit: int = ARG_VALUE_CHARS,
    *,
    exclude_reasoning: bool = False,
) -> Any:
    if isinstance(value, str):
        return _clip(redact_text(value), limit)
    if isinstance(value, Enum):
        return _safe_value(value.value, limit, exclude_reasoning=exclude_reasoning)
    if isinstance(value, Mapping):
        return {
            str(key): (
                REDACTED
                if is_sensitive_key(key)
                else _safe_value(value[key], limit, exclude_reasoning=exclude_reasoning)
            )
            for key in sorted(value, key=str)
            if not (exclude_reasoning and "reasoning" in str(key).lower())
        }
    if isinstance(value, list):
        return [_safe_value(item, limit, exclude_reasoning=exclude_reasoning) for item in value]
    if isinstance(value, tuple):
        return [_safe_value(item, limit, exclude_reasoning=exclude_reasoning) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _safe_value(
            model_dump(exclude_none=True),
            limit,
            exclude_reasoning=exclude_reasoning,
        )
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return _safe_value(attributes, limit, exclude_reasoning=exclude_reasoning)
    return str(value)


def _text_of_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        for key in ("content", "text", "detailed_content"):
            value = result.get(key)
            if isinstance(value, str):
                return value
        return str(_safe_value(result))
    for key in ("content", "detailed_content", "text"):
        value = getattr(result, key, None)
        if isinstance(value, str):
            return value
    return str(_safe_value(result))


def _label(tool: str, arguments: Any) -> str:
    if not isinstance(arguments, Mapping):
        return tool
    for key in ("command", "path", "file_path", "pattern", "query", "url"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return f"{tool}: {_clip(redact_text(' '.join(value.split())), 80)}"
    return tool


class CopilotEventNormalizer:
    """Convert Copilot events into deterministic, adapter-neutral records."""

    def __init__(self) -> None:
        self._open_tools: dict[str, dict[str, Any]] = {}
        self.final_text = ""
        self.context_tokens = 0
        self.context_window = 0
        self.usage = UsageBreakdown()

    def observe(self, event: Any) -> list[AgentEvent]:
        event_type_value = getattr(event, "type", "")
        event_type = str(getattr(event_type_value, "value", event_type_value))
        data = getattr(event, "data", None)
        if event_type == "assistant.message" and getattr(event, "agent_id", None) is None:
            self.final_text = str(getattr(data, "content", "") or "")
            return []
        if event_type == "tool.execution_start":
            self._start_tool(event)
            return []
        if event_type == "tool.execution_partial_result":
            return self._update_tool(event, "partial_results", "partial_output")
        if event_type == "tool.execution_progress":
            return self._update_tool(event, "progress", "progress_message")
        if event_type == "tool.execution_complete":
            return [self._finish_tool(event)]
        if event_type == "session.usage_info":
            self._record_usage(data)
            return []
        if event_type == "assistant.usage":
            self._record_assistant_usage(data)
            return []
        if event_type == "agent.interrupted":
            return self._interrupt_tools(event)
        if event_type == "model.call_failure":
            records = self._close_open_tools("model_call_failure")
            records.append(self._error_event(event, reason="model_call_failure"))
            return records
        if event_type == "abort":
            records = self._close_open_tools("aborted")
            records.append(self._error_event(event, reason="aborted"))
            return records
        if event_type in {"session.error", "tool.execution_error"}:
            return [self._error_event(event)]
        return []

    def _start_tool(self, event: Any) -> None:
        data = getattr(event, "data", None)
        call_id = str(getattr(data, "tool_call_id", "") or "")
        if not call_id:
            return
        existing = self._open_tools.get(call_id, {})
        arguments = getattr(data, "arguments", None)
        self._open_tools[call_id] = {
            "tool": str(getattr(data, "tool_name", "") or existing.get("tool", "tool")),
            "args": arguments if arguments is not None else existing.get("args", {}),
            "started_at": existing.get("started_at")
            or _timestamp(getattr(event, "timestamp", None)),
            "partial_results": existing.get("partial_results", []),
            "progress": existing.get("progress", []),
        }

    def _update_tool(
        self,
        event: Any,
        collection_name: str,
        field_name: str,
    ) -> list[AgentEvent]:
        data = getattr(event, "data", None)
        call_id = str(getattr(data, "tool_call_id", "") or "")
        if not call_id:
            return [
                self._error_event(
                    event,
                    reason="invalid_tool_update_id",
                    evidence={"tool_call_id": call_id},
                )
            ]
        opened = self._open_tools.get(call_id)
        if opened is None:
            return [
                self._error_event(
                    event,
                    reason="unmatched_tool_update",
                    evidence={"tool_call_id": call_id},
                )
            ]
        update = getattr(data, field_name, None)
        if update is not None:
            opened.setdefault(collection_name, []).append(_safe_value(update))
        return []

    def _finish_tool(self, event: Any) -> AgentEvent:
        data = getattr(event, "data", None)
        call_id = str(getattr(data, "tool_call_id", "") or "")
        if not call_id:
            return self._error_event(
                event,
                reason="invalid_tool_completion_id",
                evidence={
                    "tool_call_id": call_id,
                    "success": bool(getattr(data, "success", False)),
                },
            )
        opened = self._open_tools.pop(call_id, None)
        if opened is None:
            return self._error_event(
                event,
                reason="unmatched_tool_completion",
                evidence={
                    "tool_call_id": call_id,
                    "success": bool(getattr(data, "success", False)),
                },
            )
        tool = str(opened.get("tool", ""))
        arguments = opened.get("args", {})
        payload: dict[str, Any] = {
            "tool": tool,
            "tool_call_id": call_id,
            "args": _safe_value(arguments),
            "ok": bool(getattr(data, "success", False)),
            "label": _label(tool, arguments),
        }
        if opened.get("partial_results"):
            payload["partial_results"] = opened["partial_results"]
        if opened.get("progress"):
            payload["progress"] = opened["progress"]
        result = getattr(data, "result", None)
        result_text = _text_of_result(result)
        if result_text:
            payload["result_snippet"] = _clip(redact_text(result_text), RESULT_SNIPPET_CHARS)
        error = getattr(data, "error", None)
        if error is not None:
            payload["error"] = _safe_value(error)
        return AgentEvent(
            type="tool_call",
            payload=payload,
            started_at=opened.get("started_at"),
            ended_at=_timestamp(getattr(event, "timestamp", None)),
        )

    def _interrupt_tools(self, event: Any) -> list[AgentEvent]:
        data = getattr(event, "data", None)
        call_ids = [
            str(call_id) for call_id in (getattr(data, "tool_call_ids", None) or []) if str(call_id)
        ]
        if not call_ids:
            call_ids = sorted(self._open_tools)
        records: list[AgentEvent] = []
        for call_id in call_ids:
            if call_id in self._open_tools:
                records.extend(self._close_open_tools("interrupted", [call_id]))
            else:
                records.append(
                    self._error_event(
                        event,
                        reason="unmatched_tool_interruption",
                        evidence={"tool_call_id": call_id},
                    )
                )
        if not records:
            records.append(self._error_event(event, reason="agent_interrupted"))
        return records

    def _close_open_tools(
        self,
        reason: str,
        call_ids: list[str] | None = None,
    ) -> list[AgentEvent]:
        ids = sorted(call_ids if call_ids is not None else self._open_tools)
        records: list[AgentEvent] = []
        for call_id in ids:
            opened = self._open_tools.pop(call_id, None)
            if opened is None:
                continue
            payload: dict[str, Any] = {
                "reason": reason,
                "tool_call_id": call_id,
                "tool": str(opened.get("tool", "")),
                "ok": False,
                "args": _safe_value(opened.get("args", {})),
            }
            if opened.get("partial_results"):
                payload["partial_results"] = opened["partial_results"]
            if opened.get("progress"):
                payload["progress"] = opened["progress"]
            records.append(AgentEvent(type="error", payload=payload))
        return records

    def _record_usage(self, data: Any) -> None:
        current_tokens = getattr(data, "current_tokens", None)
        token_limit = getattr(data, "token_limit", None)
        if current_tokens is not None:
            self.context_tokens = int(current_tokens)
        if token_limit is not None:
            self.context_window = int(token_limit)
        self._record_usage_breakdown(data)

    def _record_assistant_usage(self, data: Any) -> None:
        self._record_usage_breakdown(data)

    def _record_usage_breakdown(self, data: Any) -> None:
        if data is None:
            return
        fields = (
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "reasoning_tokens",
            "input_cost",
            "output_cost",
            "cache_read_cost",
            "cache_write_cost",
            "total_cost",
        )
        usage = {
            field: getattr(data, field)
            for field in fields
            if getattr(data, field, None) is not None
        }
        if "total_cost" not in usage:
            cost = getattr(data, "cost", None)
            if cost is not None:
                usage["total_cost"] = cost
        if not usage:
            return
        total_tokens = getattr(data, "total_tokens", None)
        if total_tokens is None:
            total_tokens = sum(
                int(usage.get(field) or 0)
                for field in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_tokens",
                    "cache_write_tokens",
                )
            )
        self.usage.add_turn(usage, int(total_tokens))

    def _error_event(
        self,
        event: Any,
        *,
        reason: str | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> AgentEvent:
        payload = self._safe_payload(event)
        if reason is not None:
            if "reason" in payload:
                payload["event_reason"] = payload["reason"]
            payload["reason"] = reason
        if evidence:
            payload.update(
                {
                    str(key): _safe_value(value, exclude_reasoning=True)
                    for key, value in evidence.items()
                }
            )
        return AgentEvent(type="error", payload=payload)

    def _safe_payload(self, event: Any) -> dict[str, Any]:
        data = getattr(event, "data", None)
        raw_data: Any = None
        if isinstance(data, Mapping):
            raw_data = data
        else:
            model_dump = getattr(data, "model_dump", None)
            if callable(model_dump):
                raw_data = model_dump(exclude_none=True)
            else:
                attributes = getattr(data, "__dict__", None)
                if isinstance(attributes, dict):
                    raw_data = attributes
        payload: dict[str, Any] = {}
        if isinstance(raw_data, Mapping):
            for key in sorted(raw_data, key=str):
                key_text = str(key)
                if "reasoning" not in key_text.lower():
                    payload[key_text] = _safe_value(
                        raw_data[key],
                        exclude_reasoning=True,
                    )
        for key in ("error_type", "error_code", "message", "stack", "status_code", "url"):
            if key not in payload:
                value = getattr(data, key, None)
                if value is not None and "reasoning" not in key:
                    payload[key] = _safe_value(value, exclude_reasoning=True)
        if not payload:
            event_type = getattr(event, "type", "")
            payload["event"] = str(getattr(event_type, "value", event_type))
        return payload
