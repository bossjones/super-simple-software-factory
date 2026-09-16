# Examples: pointing SSSF at this repository

Each directory here is one real improvement we would ask SSSF to make to this
repository, written as a request file an ADW can consume directly, plus mock
data showing what the run is expected to produce. Read the mocks before
spending credits: they show the exact envelope, gate evidence, and trace
rows each phase yields, so you know what "working" looks like before you run
anything.

The four examples climb the chain one rung at a time:

| Example | Recipe | Agents | What it improves | Writes |
|---|---|---|---|---|
| [01-scout-stale-doc-notes](01-scout-stale-doc-notes/request.md) | `just scout` | scout | Finds stale or unfulfilled sentences in the operator docs | nothing |
| [02-plan-quality-argv-detection](02-plan-quality-argv-detection/request.md) | `just plan` | planner | Plans installer detection of the target's test command so `just sdlc` stops passing on a placeholder | `specs/` |
| [03-plan-build-kill-recipe](03-plan-build-kill-recipe/request.md) | `just plan-build` | planner, builder | Adds the `kill` recipe the run cookbook promises but the stamped justfile lacks | two files, one commit |
| [04-simple-sdlc-justfile-drift-guard](04-simple-sdlc-justfile-drift-guard/request.md) | `just simple-sdlc` | planner, builder, reviewer, documenter | Adds a test that keeps the stamped justfile and the stamped ADWs in sync | tests, three commits |

Every gap these requests name was verified against this checkout on
2026-09-15. Example 01's findings are real sentences in the current docs.
Example 03's missing recipe is real: `run_adw.md` refers to a kill helper that
nothing stamps.

## How to run one

SSSF runs against a stamped Git repository. To improve *this* repository, stamp
a scratch clone of it rather than the checkout you are editing:

```bash
SSSF_ROOT="$PWD"                                        # your SSSF checkout root
git clone --quiet "$SSSF_ROOT" /tmp/sssf-self && cd /tmp/sssf-self
uv run "$SSSF_ROOT/skills/sssf/scripts/install.py"
cp .env.sample .env                                     # then copilot login, or one token
just copilot-doctor
```

Then pass the request file by path. Every ADW accepts a path in place of
inline text:

```bash
just scout       "$SSSF_ROOT/docs/examples/01-scout-stale-doc-notes/request.md"
just plan        "$SSSF_ROOT/docs/examples/02-plan-quality-argv-detection/request.md"
just plan-build  "$SSSF_ROOT/docs/examples/03-plan-build-kill-recipe/request.md"
just simple-sdlc "$SSSF_ROOT/docs/examples/04-simple-sdlc-justfile-drift-guard/request.md"
```

Before example 04, replace the placeholder `test` argv in the scratch clone's
`adws/adw_modules/quality.py` with `["uv", "run", "pytest", "-q"]` and run
`uv sync --locked --group dev` there. Otherwise the test phase runs an `echo`
and passes vacuously. The mock `quality_result.json` shows the real command.

The stamped `protected_files` cover `adws/` in the scratch clone. The
`skills/sssf/templates/` tree is the *source* of those files and is
deliberately not protected, so examples 03 and 04 can edit it.

Read the result back:

```bash
just sessions
just phases <adw_id>
just tail <adw_id>
cat adws/adw_data/sessions/<adw_id>/*/envelope.json
```

Or open it in the [visualizer](../visualizer.md) from the SSSF checkout:

```bash
cd "$SSSF_ROOT" && just visualizer /tmp/sssf-self/adws/adw_data/sssf.db
```

If the run produced a change you want to keep, `git format-patch` it out of
the scratch clone and apply it to a branch in your real checkout. Delete
`/tmp/sssf-self` when you are done.

## What is in each `mock/` directory

The layout mirrors a real `adws/adw_data/sessions/<adw_id>/` directory plus
the SQLite rows the same run writes, so you can compare a live run against
the mock file by file.

| File | Mirrors | Shape |
|---|---|---|
| `<agent>/envelope.json` | `sessions/<adw_id>/<agent>/envelope.json` | The record SSSF writes after a valid envelope: `agent_name`, `purpose`, `output_type`, `attempt`, then every field of that output type |
| `agent_map.json` | `sessions/<adw_id>/agent_map.json` | Agent name to `{session_id, model, runtime}`; the resume key |
| `sessions.json` | `sessions` and `phases` tables | What `just sessions` and `just phases <adw_id>` print |
| `gate_results.json` | `gate_results` table | Every gate, every attempt, every `{item, ok, note}` check, including the passes |
| `events.jsonl` | `events` table | Normalized events in rowid order; the same stream `just tail` and the visualizer read |
| `quality_result.json` | the `test_1` code phase | A deterministic quality block's result, with the verbatim command and output tail |
| `planner/plan.md` | `context_handoff/plan.md` | The handoff document the builder reads |

The envelope files are validated by
[`tests/test_docs_examples.py`](../../tests/test_docs_examples.py) against the
real Pydantic models in
[`data_types.py`](../../skills/sssf/templates/adws/adw_modules/data_types.py).
If an output type gains a required field, these mocks fail the suite until
they are updated, which is the point: the examples cannot drift from the
runtime silently.

## Reading the mocks

Two details are worth noticing because they are where first-time readers get
surprised:

- **Example 03's builder ran twice.** Its first `diff_matches_claims` gate
  failed because the envelope claimed a cookbook edit that was not in the
  diff. The `events.jsonl` shows the gate failure, a `correction` log with
  `resume: true` and the same session ID, a second `apply_patch`, and then a
  pass. That is a same-session correction, not a restart. The phase row ends
  with `attempt: 2`.
- **Example 04's reviewer says `status: success` and `approved: true`, and
  those are different fields.** `status` reports that the review itself
  completed. `approved` is the verdict, and the `verdict_consistent` gate
  checks it agrees with the findings and the blocking list.

## Writing your own

Copy the closest `request.md`, keep its shape, and follow
[how_to_prompt_for_the_eng.md](../../skills/sssf/cookbooks/how_to_prompt_for_the_eng.md):
say the outcome, name the paths, state what must not change, and define
"done" as something a gate or a test can observe. A request that asks the
agent to run a command deterministic code already knows belongs in a `code`
phase, not in the prompt.
