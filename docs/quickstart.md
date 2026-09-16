# Quick start

Get from a fresh clone to a traced SSSF run in one sitting. Every command
below is real and was run against this checkout on 2026-09-15. If you want the
reasoning behind each step, read [tutorial.md](tutorial.md) instead; this page
is the short path.

## 1. Am I ready? (two minutes)

From the SSSF checkout root:

```bash
just doctor
```

`just doctor` prints the version of every tool SSSF needs and exits non-zero
if one is missing. Bun is reported but optional; it is only needed for the
[visualizer](visualizer.md).

| Tool | Why SSSF needs it | Install |
|---|---|---|
| Python 3.11+ | ADWs are Python scripts run by `uv` | [python.org](https://www.python.org/downloads/) |
| `uv` | Runs ADWs with pinned inline dependencies | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| `git` | Commit phases and the write boundary snapshot | system package manager |
| `sqlite3` | `just sessions`, `phases`, `tail`, and `procs` are SQL queries | system package manager |
| `just` | Recipe runner for both this repo and stamped targets | [just.systems](https://just.systems/) |
| `copilot` | The GitHub Copilot CLI; the SDK drives its managed runtime | [Copilot CLI docs](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli) |
| `bun` | Optional. Builds and serves the visualizer | [bun.sh](https://bun.sh/) |

Then confirm the SDK, the CLI, and the managed runtime agree with each other:

```bash
just copilot-doctor
```

This prints the CLI version, prints the pinned `github-copilot-sdk==1.0.13`
version, and stages the matching managed runtime with `download-runtime`.
If any of the three fails, stop here and read the
[troubleshooting table](tutorial.md#10-troubleshooting).

Finally, authenticate. CLI login is preferred:

```bash
copilot login
```

A local, git-ignored `.env` holding exactly one of `COPILOT_GITHUB_TOKEN`,
`GH_TOKEN`, or `GITHUB_TOKEN` is the only accepted alternative. Never put a
token in a prompt, a YAML file, or a command argument.

## 2. Is the plugin discoverable? (one minute)

From the checkout root:

```bash
copilot --no-auto-update --plugin-dir . plugin list
```

`sssf` should appear as an enabled external plugin. That is the required
discovery check. The checkout also exposes the skill through the tracked
symlink `.agents/skills/sssf`, so `copilot skill list` run from the root
shows `sssf` as a project skill without `--plugin-dir`.

Discovery changes nothing on disk. Stamping, in the next step, is what puts
the runtime into a repository.

## 3. Stamp a disposable target (three minutes)

Never stamp into this checkout while learning. Create a throwaway repository
and stamp into it from the checkout's absolute path:

```bash
SSSF_ROOT="$PWD"                      # run this from the SSSF checkout root
mkdir -p /tmp/sssf-quickstart && cd /tmp/sssf-quickstart
git init -q
git config user.email "you@example.invalid"
git config user.name "SSSF Quickstart"
uv run "$SSSF_ROOT/skills/sssf/scripts/install.py"
cp .env.sample .env
```

The installer prints every file it stamped and the three next steps. It is
idempotent: rerunning it skips files that already exist, and `--force` is the
only way to overwrite them.

What landed, and what each starter agent may write:

| Agent | Purpose | `writes` | Prompt files |
|---|---|---|---|
| `planner` | Turn a request into an implementable plan | `specs/` only | [system](../skills/sssf/templates/prompt_engineering/planner/system.md), [user](../skills/sssf/templates/prompt_engineering/planner/user.md) |
| `builder` | Implement the plan exactly | unrestricted except protected files | [system](../skills/sssf/templates/prompt_engineering/builder/system.md), [user](../skills/sssf/templates/prompt_engineering/builder/user.md) |
| `scout` | Find and report where things live | `[]`, read-only | [system](../skills/sssf/templates/prompt_engineering/scout/system.md), [user](../skills/sssf/templates/prompt_engineering/scout/user.md) |
| `reviewer` | Confirm the build matches the request | `[]`, read-only | [system](../skills/sssf/templates/prompt_engineering/reviewer/system.md), [user](../skills/sssf/templates/prompt_engineering/reviewer/user.md) |
| `documenter` | Write up the change from the diff | `docs/`, `app_docs/`, `*.md` | [system](../skills/sssf/templates/prompt_engineering/documenter/system.md), [user](../skills/sssf/templates/prompt_engineering/documenter/user.md) |

The roster itself is stamped from
[`skills/sssf/templates/sssf.config.yaml`](../skills/sssf/templates/sssf.config.yaml)
and the recipes from
[`skills/sssf/templates/justfile`](../skills/sssf/templates/justfile). The
`writes` column is enforced after every agent send by
[`permissions.py`](../skills/sssf/templates/adws/adw_modules/permissions.py);
`protected_files` (`adws/adw_modules/`, `adws/adw_sssf_config/`, `adws/adw_*.py`)
stays off limits to every agent unless its own `writes` names it.

## 4. Run the read-only smoke (five minutes, costs a few cents)

Inside the target repository:

```bash
just copilot-doctor   # the stamped copy of the same preflight
just demo
```

`just demo` runs two read-only workflows end to end: one prompt-only run with
the scout agent, then a scout recon of the target. Each prints an `adw_id`.
Nothing in the repository changes; the only new files are under
`adws/adw_data/`, which the installer already git-ignored.

Read the trace back:

```bash
just sessions
just phases <adw_id>
just tail <adw_id>
```

## 5. Run a real workflow

Prompts follow the shape in
[how_to_prompt_for_the_eng.md](../skills/sssf/cookbooks/how_to_prompt_for_the_eng.md):
outcome, affected paths, constraints, and an observable definition of done.

```bash
just plan-build "Add a file named NOTES.md at the repository root containing \
one sentence describing this scratch repo. Do not change any other file. \
Done means NOTES.md exists with exactly one sentence."
```

Every ADW also accepts a path to a prompt file instead of inline text. The
[examples directory](examples/README.md) ships ready-made request files and
the mock envelopes each phase is expected to return.

Before running `just sdlc` or `just simple-sdlc`, edit the stamped
`adws/adw_modules/quality.py` and replace the placeholder `argv` for `test`
with your real command, for example `["uv", "run", "pytest", "-q"]`. Until you
do, the test phase runs an `echo` that says so and passes.

## 6. Watch it in the visualizer (optional)

The visualizer is not stamped into targets. Run it from the SSSF checkout and
point it at the target's database:

```bash
cd "$SSSF_ROOT"
just visualizer-install
just visualizer /tmp/sssf-quickstart/adws/adw_data/sssf.db
```

Open `http://localhost:4600`. [visualizer.md](visualizer.md) covers the
two-process dev mode, ports, the JSON API, and what the server writes.

## 7. Verify the checkout itself

If you are changing SSSF rather than using it, the full credential-free gate is:

```bash
uv sync --locked --group dev
just verify
```

That runs the Ruff format check and lint, Pyright, pytest, plugin schema
validation, skill validation, Markdown link checking with `lychee`, and the
visualizer build. Use `uv run pytest -q tests/<file>.py` while iterating and
run `just verify` once before opening a pull request. `just copilot-smoke` is
the credentialed SDK create/resume smoke; run it only when lifecycle code
changes.

## Cleanup

```bash
TARGET=/tmp/sssf-quickstart
test "$TARGET" = /tmp/sssf-quickstart && rm -rf -- "$TARGET"
```

The target held the only state this page created. Nothing in the SSSF
checkout changed.

## Readiness checklist

Tick every row before asking someone else why a run failed.

- [ ] `just doctor` exits 0
- [ ] `just copilot-doctor` prints three results and no traceback
- [ ] `copilot login` succeeded, or exactly one token variable is set in a git-ignored `.env`
- [ ] `copilot --no-auto-update --plugin-dir . plugin list` shows `sssf`
- [ ] The target repository is a Git repository with no submodules and no untracked nested `.git` directories
- [ ] `just demo` in the target printed two `adw_id` values and `just sessions` lists them
- [ ] For `sdlc` chains: the `test` argv in `adws/adw_modules/quality.py` is no longer the placeholder
