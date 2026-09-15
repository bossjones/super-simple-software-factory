# Current SSSF Copilot Architecture

verified_on: 2026-09-14
scope: This page documents the current Copilot-only SSSF implementation. Historical runtime material is explicitly identified and is not a supported execution path.

## Package and installation

- The plugin manifest is [`plugin.json`](../plugin.json), and the canonical
  Agent Skill is [`skills/sssf/SKILL.md`](../skills/sssf/SKILL.md). Cookbooks,
  references, scripts, and templates are all relative to
  [`skills/sssf/`](../skills/sssf/).
- Installation is deterministic template stamping. The
  [`install.py`](../skills/sssf/scripts/install.py) script copies
  [`templates/adws/`](../skills/sssf/templates/adws/),
  [`templates/prompt_engineering/`](../skills/sssf/templates/prompt_engineering/),
  [`templates/sssf.config.yaml`](../skills/sssf/templates/sssf.config.yaml),
  [`templates/env.sample`](../skills/sssf/templates/env.sample), and the
  template [`justfile`](../skills/sssf/templates/justfile) into a target
  repository. It also adds runtime ignore rules. Session and trace directories
  are created by the first ADW run.

## Deterministic workflow control

- [`runner.py`](../skills/sssf/templates/adws/adw_modules/runner.py) owns the
  `run.phase(...)` lifecycle for engineer, agent, and deterministic code
  phases. `run.finish(accepted=...)` keeps workflow completion separate from
  acceptance.
- [`agents.py`](../skills/sssf/templates/adws/adw_modules/agents.py) renders
  prompts, calls the Copilot adapter, validates typed Pydantic envelopes,
  performs bounded JSON and gate corrections in the same session, records
  usage, and writes handoff artifacts.
- [`quality.py`](../skills/sssf/templates/adws/adw_modules/quality.py) is the
  extension seam for known lint, typecheck, build, and test commands. Those
  operations remain deterministic code rather than agent judgment.

## Copilot runtime and configuration

- [`sssf.config.yaml`](../skills/sssf/templates/sssf.config.yaml) defines
  Copilot-native defaults and per-agent overrides: model, reasoning effort,
  context tier, tools, skill directories, plugin directories, MCP servers,
  write patterns, timeouts, protected files, and the runtime data directory.
- [`agent_copilot.py`](../skills/sssf/templates/adws/adw_modules/agent_copilot.py)
  uses the pinned official Python SDK. It validates the managed runtime,
  creates or resumes caller-selected session IDs, subscribes to events before
  sending, aborts on timeout, disconnects without deleting resumable state,
  and records SDK/runtime/protocol/CLI versions.
- The SDK `available_tools` list narrows the capability surface. The installed
  permission callback returns no result for managed-approval requests and
  approve-once for ordinary requests; it is not a path-aware repository
  policy.

## Repository boundary and traces

- [`permissions.py`](../skills/sssf/templates/adws/adw_modules/permissions.py)
  snapshots the Git working tree before every Copilot turn, compares it after
  the turn, and rolls back unauthorized changes where possible. This
  post-send `writes` and protected-path enforcement is the authoritative
  repository boundary.
- [`agent_copilot.py`](../skills/sssf/templates/adws/adw_modules/agent_copilot.py)
  sanitizes raw SDK events before appending session JSONL.
  [`copilot_events.py`](../skills/sssf/templates/adws/adw_modules/copilot_events.py)
  folds SDK events into stable SSSF records, and
  [`tracer.py`](../skills/sssf/templates/adws/adw_modules/tracer.py) applies
  the same redaction policy before writing JSONL or SQLite.
- [`session.py`](../skills/sssf/templates/adws/adw_modules/session.py) creates
  the per-run directory and SQLite trace on first execution. The visualizer
  reads the normalized SQLite schema rather than raw SDK event shapes.

## Historical runtime material

The former Pi-backed implementation is historical only. Its capability
baseline and migration decisions remain in
[`pi-capability-baseline.md`](pi-capability-baseline.md) and
[`pi-to-copilot-migration-matrix.md`](pi-to-copilot-migration-matrix.md).
Those pages are migration evidence, not supported package paths,
configuration, or runtime instructions.
