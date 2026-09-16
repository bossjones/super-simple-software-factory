# Super Simple Software Factory

This repository ships the Copilot-only Agent Plugins 1.0 implementation of
SSSF. The canonical distributable surface is `skills/sssf/`: update that
directory rather than a generated target-repository copy. `plugin.json` is
the plugin manifest, and `.agents/skills/sssf` is a tracked symlink to the
same canonical skill.

## Commands

Install the pinned development environment:

```bash
uv sync --locked --group dev
```

Use the smallest relevant test while developing, including an individual test
when appropriate:

```bash
uv run pytest -q tests/test_permissions.py
uv run pytest -q tests/test_permissions.py::test_same_size_same_line_rewrite_restores_staged_and_unstaged_content
```

Repository checks:

```bash
just doctor                    # required tool presence and versions
just fmt-check                 # Ruff formatting check
just lint                      # Ruff lint
just typecheck                 # Pyright
just test                      # complete pytest suite
just visualizer-build          # Bun install plus Vue/Vite production build
just verify                    # complete local gate, including docs and plugin validation
copilot --no-auto-update --plugin-dir . plugin list  # local plugin discovery
```

`just copilot-smoke` is an opt-in credentialed create/resume SDK smoke test.
Keep it local; credential-free CI runs the deterministic checks instead.

## Architecture

- `skills/sssf/templates/` is stamped into a target repository by
  `skills/sssf/scripts/install.py`. The resulting `adws/` tree contains ADW
  entrypoints, prompt templates, roster configuration, and runtime state.
  The installer is idempotent by default and preserves destination symlinks.
- ADW entrypoints express workflows as `Run.phase(...)` blocks. They compose
  one-shot flows and chains such as plan, build, verification, review,
  documentation, and commits. `run.finish(accepted=...)` determines overall
  workflow success separately from whether individual phase blocks completed.
- `adw_modules/agents.py` validates and merges the strict YAML roster,
  renders prompts, sends typed Copilot calls, validates Pydantic envelopes,
  runs gates, and persists handoffs. Known commands such as tests, linting,
  builds, and commits belong in deterministic `kind="code"` phases rather
  than agent prompts.
- `adw_modules/agent_copilot.py` is the sole execution adapter. It manages
  the pinned Copilot SDK lifecycle and events; `runner.py` and `session.py`
  manage phase/run lifecycle; `tracer.py` writes the SQLite/JSONL evidence
  consumed by the read-only Vue visualizer in `skills/sssf/apps/visualizer/`.
- `permissions.py` is the repository write boundary. It snapshots Git state
  around every Copilot turn and compensates unauthorized changes; SDK tool
  permissions only narrow capabilities and are not the path policy.

## Control-plane contracts

- Keep `github-copilot-sdk==1.0.13` aligned across entrypoints, project
  metadata, tests, documentation, and the authenticated smoke evidence.
  Copilot client construction uses `mode="empty"` with an explicit non-empty
  tool allowlist and explicit skill enablement.
- Preserve session semantics: creation and resume are distinct operations,
  same-model agent corrections resume the existing session, and resume
  failure surfaces as a failure rather than a replacement session. Subscribe
  to events during session creation/resume, ignore startup replay when
  choosing the current response, and use only parent assistant output for an
  envelope.
- Persisted JSONL and SQLite evidence is redacted, while semantic assistant
  text stays intact until envelope parsing. Trace persistence or normalization
  failures fail the active send so successful runs always have evidence.
- Treat `permissions.enforce()` as authoritative. It preserves exact content,
  modes, symlinks, index flags, staged state, and pre-existing untracked work.
  Snapshotting fails closed around indexed submodules and pre-existing
  embedded Git repositories. In write patterns, `*` matches one directory
  level and `**` is recursive; `writes: []` is read-only and `writes: null`
  is unrestricted outside protected paths.
- Roster models reject extra fields and provider-qualified model names.
  `tools`, `writes`, protected paths, prompt paths, and timeout settings are
  configured in `skills/sssf/templates/sssf.config.yaml`; read
  `skills/sssf/references/config.md` before changing their behavior.

## Project conventions

- Keep plugin assets portable: resources referenced by `SKILL.md` stay within
  `skills/sssf/`, and the `.agents/skills/sssf` symlink continues to resolve
  to that canonical path. The layout tests enforce this packaging contract.
- The current runtime is Copilot-only. The Pi migration pages in `ai_docs/`
  provide historical evidence, not runtime implementation or configuration.
- Use `ai_docs/README.md` as the index for version-sensitive Copilot CLI,
  SDK lifecycle, event, permission, and plugin/MCP research. Refresh the
  linked primary sources when changing those integrations.
- Preserve intentional test fixtures under `tests/fixtures/`; Ruff and
  Pyright exclude them. Limit repository-wide formatting to changes that
  require it.
