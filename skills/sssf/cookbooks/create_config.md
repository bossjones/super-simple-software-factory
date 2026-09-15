# Create the roster

The generated roster is `adws/adw_sssf_config/sssf.config.yaml`:

```bash
uv run skills/sssf/scripts/make_config.py
```

The roster is Copilot-only. A minimal shape is:

```yaml
defaults:
  model: gpt-5.4
  reasoning_effort: medium
  context_tier: default
  tools: null
  skill_directories: []
  plugin_directories: []
  mcp_servers: {}
  writes: null
  timeouts:
    phase_seconds: 1800
  data_dir: adws/adw_data

agents:
  - name: planner
    model: gpt-5.4
    reasoning_effort: high
    purpose: Turn a request into an implementable plan.
    prompt_engineering:
      system: adws/adw_data/prompt_engineering/planner/system.md
      user: adws/adw_data/prompt_engineering/planner/user.md
```

Agent entries merge over defaults. `agents.validate()` checks names, prompt
files, model configuration, and runtime preflight before spawning. Models are
unqualified Copilot IDs. Only `phase_seconds` is currently enforced; optional
`tool_seconds` and `correction_seconds` fields are reserved and are not
independent enforcement controls. Output types belong at ADW call sites, not
in the roster. See [references/config.md](../references/config.md).
