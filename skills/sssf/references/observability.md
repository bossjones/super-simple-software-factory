# Observability reference

The trace path is:

```text
Copilot session events -> normalized SSSF events -> JSONL + SQLite -> UI
```

Sanitized raw Copilot event JSON is retained in each session's
`raw_output.jsonl` for diagnosis. Before persistence, SSSF recursively redacts
credential-shaped fields, configured token values, and secret-shaped strings
while retaining event types, tool names, paths, statuses, and other useful
evidence. SQLite stores normalized events behind the same sanitizer and
excludes raw reasoning content. Persisted completion events can be replayed;
ephemeral deltas and idle notifications are live telemetry.

## Normalized events

The runtime and orchestrator use these stable event names:

| Event | Meaning |
|---|---|
| `phase_start` / `phase_end` | phase lifecycle and resolved status |
| `agent_start` / `agent_end` | Copilot session lifecycle and usage |
| `tool_call` | folded tool start/update/result/failure/cancel span |
| `handoff` | typed envelope crossed to the next phase |
| `gate_pass` / `gate_fail` | gate evidence and violations |
| `log` | explicit operator or ADW message |
| `error` | native runtime or host failure |

Each event carries `adw_id` and `phase_id`. Tool calls populate
`started_at`/`ended_at`; `duration_ms` in payload is diagnostic only. Event
callbacks are installed during Copilot create/resume, before work begins.

## Runtime metadata

The `agent_end` event records per-call completion data:

- `sdk_version`
- `runtime_version`
- `protocol_version`
- detected `cli_version`
- normalized input/output/cache token and cost totals
- `context_tokens` and `context_window`

The `agent_sessions` table records the latest session/context/runtime metadata:
Copilot session ID, configured model, `context_tokens`, `context_window`,
`sdk_version`, `runtime_version`, `protocol_version`, and `cli_version`.
Task 6 is being updated to pass the runtime metadata returned by the Copilot
adapter into this row. It does not duplicate the `agent_end` usage/cost
breakdown.

Context tokens describe window occupancy, not billed spend. Usage totals in
`agent_end` include all initial, correction, and gate-retry sends.

## SQLite tables

The core tables are `sessions`, `phases`, `events`, `envelopes`,
`gate_results`, `processes`, and `agent_sessions`. `processes` tracks the
killable ADW process; the SDK does not expose a supported managed-runtime PID.
Use `just sessions`, `just phases <adw_id>`, and `just procs <adw_id>` rather
than editing rows.

Readers use WAL mode and a row cursor:

```sql
SELECT rowid, type, name, started_at, ended_at
FROM events
WHERE adw_id = ? AND rowid > ?
ORDER BY rowid
LIMIT 500;
```

Gate rows preserve every `{item, ok, note}` check, not only failures. A green
gate therefore remains explainable.

Authoritative event behavior is documented in the [SDK streaming
guide](https://github.com/github/copilot-sdk/blob/main/docs/features/streaming-events.md)
and [Python session source](https://github.com/github/copilot-sdk/blob/main/python/copilot/session.py).
