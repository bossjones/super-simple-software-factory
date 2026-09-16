# Super Simple Software Factory

SSSF is a repeatable **agents-plus-code** workflow. Deterministic Python ADWs
own sequencing, retries, gates, permissions, traceability, and acceptance;
GitHub Copilot performs the bounded work that needs reading, judgement, or code
generation.

The repository is an Agent Plugins 1.0 package. The distributable skill lives
at `skills/sssf/`; that is the canonical path for scripts, cookbooks,
references, templates, and the generated runtime.

New to SSSF? [docs/quickstart.md](docs/quickstart.md) is the short path from
a fresh clone to a traced run, starting with `just doctor`.
[docs/tutorial.md](docs/tutorial.md) is the guided, first-time walkthrough
with screenshots. [docs/visualizer.md](docs/visualizer.md) explains how to run
the observability UI, and [docs/examples/](docs/examples/README.md) holds
ready-made requests for improving this repository with SSSF, each with mock
agent output. The [docs index](docs/README.md) lists everything.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Git and a GitHub Copilot subscription/access
- `sqlite3`
- [`just`](https://just.systems/)
- [`Bun`](https://bun.sh/) only if you run the visualizer

The pinned Python dependency is
[`github-copilot-sdk==1.0.13`](https://github.com/github/copilot-sdk). SSSF
uses its public client/session API; it does not fall back to shelling out to
the CLI for agent execution.

## Quick start

### Install the plugin for Copilot discovery

This installs the published plugin for Copilot to discover. It does **not**
copy the SSSF installer or runtime into another repository:

```bash
copilot plugin install bossjones/super-simple-software-factory
```

`copilot skill list` is optional diagnostic output. Its contents and whether
plugin-provided skills appear are CLI-version-dependent; `copilot plugin list`
is the required plugin-discovery check.

### Stamp a target repository

Obtain an SSSF checkout separately, either by locating an existing checkout or
cloning one:

```bash
git clone https://github.com/bossjones/super-simple-software-factory.git \
  "$HOME/src/super-simple-software-factory"
```

From the target repository root, invoke the installer from that checkout:

```bash
uv run "$HOME/src/super-simple-software-factory/skills/sssf/scripts/install.py"
```

If the target repository is this checkout, the relative form is:

```bash
uv run skills/sssf/scripts/install.py
```

Then authenticate and run the stamped target:

```bash
copilot login
just demo
just sessions
```

The installer is idempotent: existing files are skipped. Commit or back up
local configuration before using `--force`, which refreshes stamped files.
Manual installation is a fallback when the installer checkout is unavailable.
Copy templates from a separately located SSSF checkout; plugin installation
alone does not provide these files:

```bash
SSSF_ROOT="$HOME/src/super-simple-software-factory"
mkdir -p adws/adw_data adws/adw_sssf_config
cp -R "$SSSF_ROOT/skills/sssf/templates/adws/." adws/
cp -R "$SSSF_ROOT/skills/sssf/templates/prompt_engineering" adws/adw_data/
cp "$SSSF_ROOT/skills/sssf/templates/sssf.config.yaml" \
  adws/adw_sssf_config/sssf.config.yaml
cp "$SSSF_ROOT/skills/sssf/templates/env.sample" .env.sample
cp "$SSSF_ROOT/skills/sssf/templates/justfile" justfile
```

Copy only the files needed by the target repository and preserve local
customizations. The installer is the preferred path because it also adds the
target-repository ignore rules. Session and trace directories are created on
the first ADW run.

### Local plugin development

Do not pass a local directory to `copilot plugin install`. Validate an
uninstalled checkout with the CLI's plugin directory option instead:

```bash
copilot --plugin-dir /path/to/super-simple-software-factory plugin list
```

From this checkout, the equivalent commands are:

```bash
copilot --no-auto-update --plugin-dir . plugin list
```

The plugin listing should show `sssf` as an enabled external plugin. Optionally
run `skill list --json` or invoke the skill; either result is
CLI-version-dependent and plugin-provided skills may not appear in the list.
Avoid enabling another active copy of the same skill while testing.

This checkout also carries a tracked symlink `.agents/skills/sssf` that
resolves to `skills/sssf/`, so `copilot skill list` run from the repository
root lists `sssf` under project skills without `--plugin-dir`. If the
published plugin is installed as well, Copilot loads the skill twice while
working inside the checkout. Windows clones need `git config core.symlinks
true` before checkout, otherwise the link is a plain text file.

## SDK and runtime preflight

Run these checks before a first ADW run or after updating the SDK/CLI:

```bash
copilot --version
uv run --with github-copilot-sdk==1.0.13 python -c \
  "import importlib.metadata as m; print(m.version('github-copilot-sdk'))"
uv run --with github-copilot-sdk==1.0.13 python -m copilot download-runtime
```

The SDK adapter validates the installed SDK and the managed runtime protocol
before an agent phase starts. The expected SDK release is pinned in the
generated ADW entry points and project metadata. `download-runtime` stages the
matching managed runtime; the SDK can otherwise download it on first use.
CLI login is preferred. A local ignored `.env` is also an accepted token store
for the variables in `.env.sample`; never commit `.env` or put tokens in
prompts, YAML, or CLI arguments.

See the official [Copilot CLI command
reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference),
[Python SDK README](https://github.com/github/copilot-sdk/blob/main/python/README.md),
and [SDK repository](https://github.com/github/copilot-sdk).

## Run an ADW

Run from the target repository root:

```bash
uv run adws/adw_plan.py "add a health endpoint"
uv run adws/adw_plan_build.py requests/health.md
uv run adws/adw_simple_sdlc.py "implement the health endpoint"
```

Use `--config path/to/sssf.config.yaml` for a non-default roster and
`--adw-id ID` to join an existing SSSF session. `just demo` runs a small
credentialed smoke path; `just sessions`, `just phases ID`, and `just procs ID`
inspect the resulting trace. A known command belongs in a deterministic
`kind="code"` phase, not in an agent prompt.

### Sessions and corrections

The first call creates a caller-selected Copilot session ID. Later phases,
parse corrections, and gate corrections resume that same session. SSSF stores
the mapping in `adws/adw_data/sessions/{adw_id}/agent_map.json` and keeps the
raw event stream beside the envelope. A model change intentionally starts a
fresh session rather than resuming context created by another model.

`send_and_wait()` only bounds waiting. On a phase deadline the runtime calls
`session.abort()` explicitly, then disconnects without deleting resumable
state. Resume failures are reported; they are never silently replaced with a
new session. See the [session persistence
guide](https://github.com/github/copilot-sdk/blob/main/docs/features/session-persistence.md)
and [streaming events guide](https://github.com/github/copilot-sdk/blob/main/docs/features/streaming-events.md).

## Configuration

The generated file is `adws/adw_sssf_config/sssf.config.yaml`. Common fields
are:

```yaml
defaults:
  model: gpt-5.4
  reasoning_effort: medium
  context_tier: default
  tools: [view, rg, glob, bash, apply_patch]
  skill_directories: []
  plugin_directories: []
  mcp_servers: {}
  writes: null
  timeouts:
    phase_seconds: 1800
    tool_seconds: 300
    correction_seconds: 300
  data_dir: adws/adw_data
```

Agent entries inherit defaults and may override model, reasoning effort,
context tier, tools, skill/plugin directories, MCP servers, `writes`, and
timeouts. Models are unqualified Copilot model IDs such as `gpt-5.4`.
`tools` must be an explicit non-empty Copilot allowlist because the adapter
uses SDK empty mode; there is no implicit "all tools" value. `writes` is the
authoritative repository boundary, while `tools` narrows capabilities.
`protected_files` remains off limits unless explicitly unlocked for that
agent. Only `phase_seconds` is currently enforced as a timeout.
`tool_seconds` and `correction_seconds` are reserved fields, not independent
enforcement controls. Read [references/config.md](skills/sssf/references/config.md)
before changing a roster.

## Skills, plugins, MCP, and permissions

- `SKILL.md` follows the open [Agent Skills
  specification](https://agentskills.io/specification). Project skills are
  discovered from supported skill directories; SSSF's packaged skill is under
  `skills/sssf/`. A tracked symlink at `.agents/skills/sssf` points to that
  directory so a plain checkout also exposes it as a project skill.
- A plugin may bundle skills, agents, hooks, MCP, and LSP resources. The
  `plugin.json` manifest follows the [Agent Plugins 1.0
  specification](https://github.com/agentplugins/agent-plugins-spec/blob/main/spec/1.0.0.md).
- MCP servers are configured with the SDK's `mcp_servers` field or Copilot's
  documented project/user configuration. Review server commands and
  permissions before enabling them.
- Use the narrowest available tools and URLs. Copilot permissions, hooks, and
  sandboxes reduce risk but do not prove that repository writes stayed within
  policy. SSSF's before/after snapshot and rollback check is authoritative.

Official references: [Agent Skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills),
[Copilot plugins](https://docs.github.com/en/copilot/concepts/agents/about-plugins),
[MCP servers](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers),
[permissions](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference),
and [hooks](https://docs.github.com/en/copilot/concepts/agents/hooks).

## Breaking migration

This is a breaking harness migration. Existing generated repositories are not
silently rewritten. Reinstall or migrate them deliberately, then run the
verification commands below.

| Historical surface | Copilot-native replacement |
|---|---|
| Former agent-runtime selector | Copilot is the only supported runtime; remove the selector |
| Former thinking setting | `reasoning_effort` |
| Former extension bundle setting | `skill_directories`, `plugin_directories`, and `mcp_servers` |
| Provider-qualified model IDs | Unqualified Copilot model IDs |
| Former runtime/path environment variables | `COPILOT_CLI_PATH` and `COPILOT_HOME` |
| Former agent adapter and extensions | `agent_copilot.py` and public SDK configuration |

Do not copy old runtime directories into a new installation. Preserve old
SQLite traces for historical analysis, but do not expect old session state to
resume under a changed model or runtime. The [migration
matrix](ai_docs/pi-to-copilot-migration-matrix.md) is a historical comparison,
not a supported second runtime.

## Troubleshooting

1. **Plugin or skill is missing:** run the local `--plugin-dir` commands from
   the repository root; confirm `plugin.json` and `skills/sssf/SKILL.md` are
   inside the checkout.
2. **SDK preflight fails:** compare `copilot --version`, the pinned SDK
   version, and the managed runtime. Repeat both SDK commands with
   `uv run --with github-copilot-sdk==1.0.13 ...`.
3. **Authentication fails:** prefer `copilot login`; alternatively use the
   documented token variables in a local ignored `.env`. Never commit `.env` or
   put a token in YAML, prompts, command arguments, or trace artifacts.
4. **A resume fails:** keep the recorded session ID for diagnosis. Check the
   runtime and model; do not replace the ID with a new session manually.
5. **A run times out:** inspect the phase and process rows with
   `just phases ID`, `just tail ID`, and `just procs ID`. Verify the PID and
   recorded command shown by `just procs ID` before terminating the ADW process
   using the host operating system's process controls. The runtime aborts
   active Copilot work before cleanup.
6. **A gate or permission fails:** read the gate evidence and changed-path
   report. Fix the agent prompt/configuration or the work product, then rerun;
   do not edit envelopes or trace rows by hand.

## Verification

Toolchain check (prints every required tool's version, exits non-zero if one
is missing):

```bash
just doctor
just copilot-doctor
```

Credential-free checks:

```bash
just verify
```

This runs the Ruff format check and lint, Pyright, pytest, plugin schema
validation, Markdown link validation, and the visualizer build.

With Copilot authentication and entitlement available, also run the opt-in
runtime smoke:

```bash
just copilot-smoke
```

The live smoke covers authenticated SDK create/disconnect, a read-only turn,
event capture, and a same-session resumed correction. Deterministic tests, not
model behavior, verify allowed writes and unauthorized-write rollback.

Local plugin discovery:

```bash
copilot --no-auto-update --plugin-dir . plugin list
```

`skill list --json` is optional and version-dependent; plugin discovery is
established by `plugin list`. The optional authenticated smoke path is
`just demo`. The stamped target's supported observation commands are
`just sessions`, `just phases ID`, `just tail ID`, and `just procs ID`; the
visualizer is not installed by the factory installer. Run it from this
checkout with `just visualizer path/to/sssf.db`; see
[docs/visualizer.md](docs/visualizer.md). For the factual basis
of the runtime and operational guidance, start with
[ai_docs/README.md](ai_docs/README.md), then read the smallest relevant
reference. Refresh version-sensitive links against the official [CLI
docs](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli)
and [Python SDK docs](https://github.com/github/copilot-sdk) before changing
the integration.
