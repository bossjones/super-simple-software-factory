# SSSF overview

SSSF is a control plane for repeatable agents-plus-code delivery. An ADW
sequences engineer, Copilot agent, and deterministic code phases:

```text
ADW -> Run.phase -> agents.execute -> Copilot Python SDK -> session/events
                         |              |
                         v              v
                   typed envelopes   SQLite + raw JSONL
```

The plugin source is under `skills/sssf/`. A stamped target repository has:

```text
adws/
  adw_*.py
  adw_modules/
  adw_sssf_config/sssf.config.yaml
  adw_data/
    prompt_engineering/
    sessions/{adw_id}/
    sssf.db
```

ADW phases are `engineer`, `agent`, or `code`. Agent phases use one bounded
Copilot prompt and a typed envelope. Code phases run known commands such as
tests, diffs, migrations, or commits. Every run ends with explicit
`run.finish(accepted=...)`.

The first call creates a caller-selected session ID. Later calls and
corrections resume it. Copilot events are subscribed during create/resume,
normalized into SSSF events, and retained raw for diagnosis. Session idle is
the mechanical completion signal; deadline handling calls `abort()`.

Read [references/config.md](../references/config.md) for the roster,
[references/handoff.md](../references/handoff.md) for envelopes and sessions,
and [references/observability.md](../references/observability.md) for SQLite.

First time here? [../../../docs/tutorial.md](../../../docs/tutorial.md) walks
through this shape end to end against a disposable target repository.
