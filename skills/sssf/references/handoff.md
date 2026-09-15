# Handoff reference

Each Copilot agent has two output channels:

1. files in `context_handoff/`;
2. one final JSON object parsed against the declared Pydantic envelope.

The host persists the envelope and renders it into the next prompt. A response
that is malformed, schema-invalid, or fails a gate is corrected in the same
Copilot session, with bounded attempts. It is never converted into success and
never restarted cold.

## Envelope

Every output extends:

```python
class EnvelopeBase(BaseModel):
    status: Literal["success", "fail"]
    summary: str = ""
    artifacts: list[str] = []
    notes_for_next_agent: str = ""
```

The output type, the prompt's `## Report` JSON example, and the ADW
`output_type=` argument are a synced triad. Keep all three aligned.

## Session layout

```text
adws/adw_data/sessions/{adw_id}/
  agent_map.json
  context_handoff/
  {agent}/
    prompts/
    copilot/
    raw_output.jsonl
    envelope.json
```

`agent_map.json` maps an SSSF agent name to its Copilot session ID and model.
The first call creates the caller-selected session. Later phases and
corrections resume that exact ID. A resume failure is explicit; the runtime
does not silently create a replacement. `disconnect()` preserves resumable
state, while destructive deletion is not part of normal cleanup.

The runtime subscribes with `on_event=` during both create and resume so
startup events are not lost. `session.idle` marks mechanical completion.
`send_and_wait(timeout=...)` bounds the wait only; timeout handling calls
`session.abort()` before cleanup.

Reference the [SDK persistence guide](https://github.com/github/copilot-sdk/blob/main/docs/features/session-persistence.md)
and [streaming events guide](https://github.com/github/copilot-sdk/blob/main/docs/features/streaming-events.md)
when version-sensitive behavior matters.
