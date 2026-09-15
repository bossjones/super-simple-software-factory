# Configuration reference

The generated configuration is
`adws/adw_sssf_config/sssf.config.yaml`. It is loaded from the target
repository; `--config` selects another file.

## Defaults and fields

```yaml
defaults:
  model: gpt-5.4
  reasoning_effort: medium
  context_tier: default
  color: ""
  tools: [view, rg, glob, bash, apply_patch]
  skill_directories: []
  plugin_directories: []
  mcp_servers: {}
  writes: null
  timeouts:
    phase_seconds: 1800
  protected_files:
    - adws/adw_modules/
    - adws/adw_sssf_config/
    - adws/adw_*.py
  data_dir: adws/adw_data

observability:
  db: adws/adw_data/sssf.db
  poll_ms: 500
```

`model` is an unqualified Copilot model ID. `reasoning_effort` is one of
`none`, `minimal`, `low`, `medium`, `high`, `xhigh`, or `max`.
`context_tier` is `default` or `long_context`. `tools` must be an explicit,
non-empty SDK allowlist because SSSF uses `mode="empty"`; `null` and `[]` are
rejected rather than interpreted as "all tools."

`skill_directories` and `plugin_directories` add Copilot discovery roots.
When `skill_directories` is non-empty, SSSF explicitly enables SDK skill
loading. Explicit plugin directories are passed on both create and resume.
`mcp_servers` is passed to the SDK as configured. Validate every server and its
permissions before enabling it.

`writes` is the repository write policy: omitted/`null` is unrestricted except
for protected files, `[]` is read-only with respect to the repository, and a
list uses exact paths plus `/`, `*`, and `**` patterns. `protected_files`
cannot be changed unless the agent explicitly names the path in `writes`.
The SDK receives `tools` as `available_tools`. The callback returns no result
for managed-approval requests and approves ordinary permission requests once.
The tool list narrows capabilities, but the callback is not path-aware. SSSF
enforces `writes` after every turn by comparing and, where possible, rolling
back changed paths.

`phase_seconds` is the only timeout currently enforced: it bounds the phase,
and the runtime calls `session.abort()` when the deadline expires. If present,
`tool_seconds` and `correction_seconds` are reserved for future independent
budgets; they are not currently enforced. Waiting alone does not cancel work.

## Agent entries and merging

Each agent requires `name`, `purpose`, and `prompt_engineering.system` plus
`.user`. Other fields override `defaults`:

```yaml
agents:
  - name: planner
    model: gpt-5.4
    reasoning_effort: high
    purpose: Turn a request into an implementable plan.
    prompt_engineering:
      system: adws/adw_data/prompt_engineering/planner/system.md
      user: adws/adw_data/prompt_engineering/planner/user.md
    writes: ["specs/**"]
```

Defaults are merged before strict validation. Nested `timeouts` merge
field-by-field. Missing agents, prompt files, unsupported fields, malformed
models, or failed SDK/runtime preflight stop the run before an agent starts.

Changing an agent's model invalidates its stored session because context built
by one model must not be resumed by another. The map is retained for diagnosis;
the next call creates a fresh caller-selected session. Reasoning, color, and
timeout changes do not invalidate a session.

## SDK preflight

```bash
copilot --version
uv run --with github-copilot-sdk==1.0.13 python -c \
  "import importlib.metadata as m; print(m.version('github-copilot-sdk'))"
uv run --with github-copilot-sdk==1.0.13 python -m copilot download-runtime
```

The runtime adapter checks the pinned SDK release and public runtime protocol,
then records SDK, runtime, protocol, and detected CLI versions. It uses
`CopilotClient` with `mode="empty"` and public lifecycle methods only.

Authoritative sources: [Python SDK
README](https://github.com/github/copilot-sdk/blob/main/python/README.md),
[session persistence](https://github.com/github/copilot-sdk/blob/main/docs/features/session-persistence.md),
[CLI programmatic reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference),
and [MCP servers](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers).
