# Super Simple Software Factory

SSSF is a Copilot-only Agent Plugins 1.0 package. Deterministic Python ADWs own
orchestration, gates, permissions, retries, and tracing; the GitHub Copilot SDK
performs bounded agent work.

## Commands

| Command | Purpose |
|---|---|
| `uv sync --locked --group dev` | Install pinned development dependencies |
| `just doctor` | Print required tool versions; exits non-zero if one is missing |
| `just visualizer path/to/sssf.db` | Build and serve the visualizer against a target's trace db on port 4600 |
| `just verify` | Run formatting checks, Ruff, Pyright, tests, plugin/skill validation, link checks, and visualizer build |
| `uv run pytest -q tests/<file>.py` | Run the smallest relevant test target while developing |
| `just copilot-smoke` | Run the credentialed create/resume SDK smoke locally; never add it to credential-free CI |
| `copilot --no-auto-update --plugin-dir . plugin list` | Validate local plugin discovery |

## Architecture

- `skills/sssf/` is the canonical distributable skill and plugin content.
- `skills/sssf/templates/adws/adw_modules/` is the deterministic control plane.
- `agent_copilot.py` owns SDK lifecycle; `agents.py` owns phase orchestration;
  `permissions.py` is the authoritative repository write boundary; `tracer.py`
  owns persisted evidence.
- `ai_docs/` contains grounded, agent-oriented references. Verify
  version-sensitive SDK claims against linked primary sources.
- `scripts/copilot_smoke.py` validates live create plus same-session resume
  behavior.

## Runtime invariants

- Keep `github-copilot-sdk==1.0.13` pinned unless updating implementation,
  documentation, tests, and smoke evidence together.
- Use `CopilotClient(mode="empty")` with explicit non-empty tools and explicit
  skill enablement.
- Create and resume are distinct: failed resume must never silently create a
  replacement session.
- Pass event handlers during session creation/resume, discard startup replay
  text, and accept only parent assistant output for envelopes.
- Redact only persisted JSONL/SQLite evidence; never mutate semantic assistant
  text before envelope parsing.
- `permissions.enforce()` is authoritative. Preserve exact bytes, modes,
  symlinks, staged state, index flags, and pre-existing untracked work.
- Repositories containing indexed submodules or untracked embedded Git
  repositories fail closed before agent execution. Never recursively delete a
  pre-existing nested repository.

## Efficient change workflow

1. Freeze scope and measurable acceptance criteria before implementation.
   Classify additional hardening as follow-up work unless it blocks those
   criteria.
2. Timebox research to the facts needed for the change. Run independent
   research or implementation streams in parallel with explicit file
   ownership.
3. Use test-driven fixes: reproduce the defect, run the focused test and
   observe failure, implement minimally, then rerun that target.
4. Do not run `just verify` after every small edit. Use targeted tests during
   development and run the full gate once the integrated candidate is ready.
5. Request one comprehensive review with the complete threat model; avoid
   serial one-finding review loops.
6. Do not apply repository-wide formatting unless required. Immutable
   historical fixtures under `tests/fixtures/` are excluded from Ruff/Pyright.
7. Open a draft PR after the first integrated green build when work will
   continue, so CI and review run concurrently.

## Completion checklist

- Run targeted tests for changed behavior, then `just verify` once.
- Run `just copilot-smoke` only when SDK lifecycle behavior changes or before
  release.
- Run `git diff --check` and inspect the staged diff.
- Preserve unrelated worktree changes; stage intended paths explicitly rather
  than using `git add .` or `git add -A`.
- A change is complete when required behavior is verified and persisted, not
  when every possible defense-in-depth idea has been folded into the same PR.
