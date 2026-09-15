from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

from adw_modules.copilot_events import CopilotEventNormalizer
from copilot.session_events import (
    AbortData,
    AbortReason,
    AgentInterruptedActivity,
    AgentInterruptedData,
    AssistantMessageData,
    AssistantReasoningDeltaData,
    AssistantUsageData,
    ModelCallFailureData,
    ModelCallFailureSource,
    SessionErrorData,
    SessionEvent,
    SessionEventType,
    SessionUsageInfoData,
    ToolExecutionCompleteData,
    ToolExecutionCompleteError,
    ToolExecutionCompleteResult,
    ToolExecutionPartialResultData,
    ToolExecutionProgressData,
    ToolExecutionStartData,
)


def sdk_event(
    event_type,
    data,
    *,
    event_id="00000000-0000-0000-0000-000000000001",
    agent_id=None,
    timestamp="2026-09-14T12:00:00+00:00",
):
    return SessionEvent(
        type=event_type,
        id=UUID(event_id),
        timestamp=datetime.fromisoformat(timestamp),
        agent_id=agent_id,
        data=data,
    )


def lightweight_event(event_type: str, **data):
    return SimpleNamespace(
        type=event_type,
        id=data.pop("id", "event-1"),
        agent_id=data.pop("agent_id", None),
        timestamp=data.pop("timestamp", "2026-09-14T12:00:00Z"),
        data=SimpleNamespace(**data),
    )


def test_tool_execution_is_folded_into_one_record():
    normalizer = CopilotEventNormalizer()
    assert (
        normalizer.observe(
            sdk_event(
                SessionEventType.TOOL_EXECUTION_START,
                ToolExecutionStartData(
                    tool_call_id="call-1",
                    tool_name="view",
                    arguments={"path": "README.md"},
                ),
            )
        )
        == []
    )

    records = normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            ToolExecutionCompleteData(
                tool_call_id="call-1",
                result=ToolExecutionCompleteResult(content="contents"),
                success=True,
            ),
            timestamp="2026-09-14T12:00:01+00:00",
        )
    )

    assert len(records) == 1
    assert records[0].type == "tool_call"
    assert records[0].payload["tool_call_id"] == "call-1"
    assert records[0].payload["ok"] is True


def test_parent_final_message_wins_over_subagent_message():
    normalizer = CopilotEventNormalizer()
    normalizer.observe(
        sdk_event(
            SessionEventType.ASSISTANT_MESSAGE,
            AssistantMessageData(content="child", message_id="child"),
            agent_id="agent-1",
        )
    )
    normalizer.observe(
        sdk_event(
            SessionEventType.ASSISTANT_MESSAGE,
            AssistantMessageData(content="parent", message_id="parent"),
        )
    )
    assert normalizer.final_text == "parent"


def test_reasoning_events_are_not_normalized():
    normalizer = CopilotEventNormalizer()
    assert (
        normalizer.observe(
            sdk_event(
                SessionEventType.ASSISTANT_REASONING_DELTA,
                AssistantReasoningDeltaData(delta_content="secret", reasoning_id="reason-1"),
            )
        )
        == []
    )


def test_tool_record_uses_event_timestamps_and_clips_strings():
    normalizer = CopilotEventNormalizer()
    long_text = "x" * 20_001
    normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_START,
            ToolExecutionStartData(
                tool_call_id="call-1",
                tool_name="view",
                arguments={"path": long_text, "nested": [long_text]},
            ),
            timestamp="2026-09-14T12:00:01+00:00",
        )
    )

    record = normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            ToolExecutionCompleteData(
                tool_call_id="call-1",
                result=ToolExecutionCompleteResult(content=long_text),
                success=False,
            ),
            timestamp="2026-09-14T12:00:02+00:00",
        )
    )[0]

    assert record.started_at == "2026-09-14T12:00:01+00:00"
    assert record.ended_at == "2026-09-14T12:00:02+00:00"
    assert record.payload["args"]["path"].endswith("…")
    assert len(record.payload["args"]["path"]) == 20_001
    assert record.payload["args"]["nested"][0].endswith("…")
    assert record.payload["result_snippet"].endswith("…")
    assert len(record.payload["result_snippet"]) == 20_001


def test_usage_info_updates_context_without_emitting_an_event():
    normalizer = CopilotEventNormalizer()
    assert (
        normalizer.observe(
            sdk_event(
                SessionEventType.SESSION_USAGE_INFO,
                SessionUsageInfoData(current_tokens=123, messages_length=1, token_limit=456),
            )
        )
        == []
    )
    assert normalizer.context_tokens == 123
    assert normalizer.context_window == 456


def test_sdk_usage_fields_are_accumulated():
    normalizer = CopilotEventNormalizer()
    assert (
        normalizer.observe(
            sdk_event(
                SessionEventType.ASSISTANT_USAGE,
                AssistantUsageData(
                    model="gpt-5.4",
                    input_tokens=10,
                    output_tokens=20,
                    cache_read_tokens=3,
                    cache_write_tokens=4,
                    reasoning_tokens=5,
                    cost=0.25,
                ),
            )
        )
        == []
    )
    assert normalizer.usage.input_tokens == 10
    assert normalizer.usage.output_tokens == 20
    assert normalizer.usage.cache_read_tokens == 3
    assert normalizer.usage.cache_write_tokens == 4
    assert normalizer.usage.reasoning_tokens == 5
    assert normalizer.usage.total_tokens == 37
    assert normalizer.usage.total_cost == 0.25


def test_errors_are_normalized_without_reasoning_payload():
    normalizer = CopilotEventNormalizer()
    records = normalizer.observe(
        sdk_event(
            SessionEventType.SESSION_ERROR,
            SessionErrorData(error_type="runtime", message="failed", stack="trace"),
        )
    )
    assert len(records) == 1
    assert records[0].type == "error"
    assert records[0].payload["message"] == "failed"
    assert "reasoning_text" not in records[0].payload


def test_missing_or_unpaired_completion_is_an_error_not_a_successful_tool_call():
    normalizer = CopilotEventNormalizer()
    missing_id = normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            ToolExecutionCompleteData(
                tool_call_id="",
                result=ToolExecutionCompleteResult(content="contents"),
                success=True,
            ),
        )
    )
    unpaired = normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            ToolExecutionCompleteData(
                tool_call_id="missing",
                result=ToolExecutionCompleteResult(content="contents"),
                success=True,
            ),
        )
    )

    assert [record.type for record in missing_id + unpaired] == ["error", "error"]
    assert all(record.payload.get("ok") is not True for record in missing_id + unpaired)
    assert missing_id[0].payload["reason"] == "invalid_tool_completion_id"
    assert unpaired[0].payload["reason"] == "unmatched_tool_completion"


def test_partial_results_and_progress_are_folded_into_completed_tool_record():
    normalizer = CopilotEventNormalizer()
    normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_START,
            ToolExecutionStartData(tool_call_id="call-1", tool_name="bash", arguments={}),
        )
    )
    assert (
        normalizer.observe(
            sdk_event(
                SessionEventType.TOOL_EXECUTION_PARTIAL_RESULT,
                ToolExecutionPartialResultData(partial_output="part", tool_call_id="call-1"),
            )
        )
        == []
    )
    assert (
        normalizer.observe(
            sdk_event(
                SessionEventType.TOOL_EXECUTION_PROGRESS,
                ToolExecutionProgressData(progress_message="working", tool_call_id="call-1"),
            )
        )
        == []
    )

    records = normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            ToolExecutionCompleteData(
                tool_call_id="call-1",
                result=ToolExecutionCompleteResult(content="done"),
                success=True,
            ),
        )
    )

    assert len(records) == 1
    assert records[0].payload["partial_results"] == ["part"]
    assert records[0].payload["progress"] == ["working"]
    late_update = normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_PROGRESS,
            ToolExecutionProgressData(progress_message="late", tool_call_id="call-1"),
        )
    )
    assert late_update[0].type == "error"
    assert late_update[0].payload["reason"] == "unmatched_tool_update"


def test_interruption_closes_open_tools_and_later_completion_cannot_duplicate():
    normalizer = CopilotEventNormalizer()
    normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_START,
            ToolExecutionStartData(tool_call_id="call-1", tool_name="bash", arguments={}),
        )
    )
    interrupted = normalizer.observe(
        sdk_event(
            SessionEventType.AGENT_INTERRUPTED,
            AgentInterruptedData(
                activity=AgentInterruptedActivity.TOOL_CALL,
                elapsed=timedelta(seconds=1),
                turn=1,
                tool_call_ids=["call-1"],
            ),
        )
    )
    duplicate = normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            ToolExecutionCompleteData(tool_call_id="call-1", success=True),
        )
    )

    assert len(interrupted) == 1
    assert interrupted[0].type == "error"
    assert interrupted[0].payload["reason"] == "interrupted"
    assert interrupted[0].payload["ok"] is False
    assert duplicate[0].type == "error"
    assert duplicate[0].payload["reason"] == "unmatched_tool_completion"


def test_model_failure_and_abort_are_explicit_errors_without_reasoning():
    normalizer = CopilotEventNormalizer()
    model_failure = normalizer.observe(
        sdk_event(
            SessionEventType.MODEL_CALL_FAILURE,
            ModelCallFailureData(
                source=ModelCallFailureSource.TOP_LEVEL,
                error_message="model failed",
                reasoning_effort="high",
            ),
        )
    )
    abort = normalizer.observe(
        sdk_event(
            SessionEventType.ABORT,
            AbortData(reason=AbortReason.USER_ABORT),
        )
    )

    assert model_failure[0].type == "error"
    assert model_failure[0].payload["reason"] == "model_call_failure"
    assert model_failure[0].payload["error_message"] == "model failed"
    assert "reasoning_effort" not in model_failure[0].payload
    assert abort[0].type == "error"
    assert abort[0].payload["reason"] == "aborted"
    assert abort[0].payload["event_reason"] == "user_abort"


def test_abort_closes_open_tools_as_errors():
    normalizer = CopilotEventNormalizer()
    normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_START,
            ToolExecutionStartData(tool_call_id="call-1", tool_name="bash", arguments={}),
        )
    )
    records = normalizer.observe(
        sdk_event(
            SessionEventType.ABORT,
            AbortData(reason=AbortReason.USER_ABORT),
        )
    )
    assert [record.type for record in records] == ["error", "error"]
    assert records[0].payload["tool_call_id"] == "call-1"
    assert records[0].payload["ok"] is False
    assert records[1].payload["reason"] == "aborted"


def test_failed_completion_preserves_typed_error_evidence():
    normalizer = CopilotEventNormalizer()
    normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_START,
            ToolExecutionStartData(tool_call_id="call-1", tool_name="bash", arguments={}),
        )
    )
    record = normalizer.observe(
        sdk_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            ToolExecutionCompleteData(
                tool_call_id="call-1",
                success=False,
                error=ToolExecutionCompleteError(message="command failed", code="E_FAIL"),
            ),
        )
    )[0]
    assert record.type == "tool_call"
    assert record.payload["ok"] is False
    assert record.payload["error"]["message"] == "command failed"


def test_unknown_events_are_ignored():
    assert CopilotEventNormalizer().observe(lightweight_event("future.event", secret="value")) == []
