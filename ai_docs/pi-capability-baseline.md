# Pi Capability Baseline

verified_on: 2026-09-14
historical: true
scope: This historical page records the Pi features the pre-Copilot SSSF v1 depended on and does not describe the supported runtime.

- Pi is a minimal terminal coding harness that stays small at the core and extends itself through TypeScript extensions, skills, prompt templates, themes, and packages; source: [Pi documentation index](https://pi.dev/docs/latest) and the [Pi repository](https://github.com/earendil-works/pi).
- Pi exposes the exact non-interactive surfaces SSSF v1 leans on: print mode (`-p/--print`), JSON event stream mode (`--mode json`), and RPC mode (`--mode rpc`); source: [Using Pi](https://pi.dev/docs/latest/usage), [JSON Event Stream Mode](https://pi.dev/docs/latest/json), and [RPC Mode](https://pi.dev/docs/latest/rpc).
- Pi sessions are automatically saved under `~/.pi/agent/sessions/` unless `--no-session` is used, and Pi also exposes `--continue`, `--resume`, explicit `--session`, and `--fork` flows for reusing or branching conversation state; source: [Using Pi](https://pi.dev/docs/latest/usage).
- Pi's JSON event stream is already close to what SSSF needs for tracing: it emits JSONL, streams delta-style `message_update` records, and finishes with authoritative `message_end`, `turn_end`, and `agent_end` events; source: [JSON Event Stream Mode](https://pi.dev/docs/latest/json).
- Pi RPC mode supports prompt submission, steering, follow-up queuing, explicit `abort`, queue clearing, and state inspection over JSONL stdin/stdout, which is why SSSF could treat Pi as a headless runtime instead of a human-only TUI; source: [RPC Mode](https://pi.dev/docs/latest/rpc).
- Pi extensions are powerful enough to shape harness behavior directly: they can intercept events, block or modify tool calls, register new tools and commands, manage session-scoped state, and execute custom UI; source: [Extensions](https://pi.dev/docs/latest/extensions).
- Pi skills already implement the open Agent Skills standard, but Pi deliberately remains lenient about some standard violations such as directory-name matching. That matters during porting because Copilot support should follow the standard more closely than Pi's compatibility layer; source: [Skills](https://pi.dev/docs/latest/skills) and the [Agent Skills specification](https://agentskills.io/specification).
- Pi does not provide a built-in filesystem/process/network permission system. The upstream repo states that Pi runs with the permissions of the launching user/process and recommends containerization or sandboxing when stronger boundaries are required; source: the [Pi repository](https://github.com/earendil-works/pi) and [Extensions](https://pi.dev/docs/latest/extensions).
- Pi has its own project-trust model for loading project-local resources, but that trust gate is separate from SSSF's repo write policy. Pi loads project resources only after trust is established and gives non-interactive modes default trust fallbacks through settings or flags; source: [Using Pi](https://pi.dev/docs/latest/usage).

Refresh from the Pi docs pages above before removing or translating a v1 capability, because later tasks depend on knowing what SSSF already gets from Pi today.
