# Update configuration

Edit `adws/adw_sssf_config/sssf.config.yaml` deliberately. Agent entries
inherit defaults; a nested timeout override merges field by field.

```yaml
agents:
  - name: builder
    model: gpt-5.4
    reasoning_effort: high
    context_tier: long_context
    tools: [view, grep, glob, bash]
    skill_directories: []
    plugin_directories: []
    mcp_servers: {}
    writes: ["src/**", "tests/**"]
    timeouts:
      phase_seconds: 1800
```

Use the narrowest tools, MCP servers, URLs, and write patterns needed. Model
changes invalidate the recorded session for that agent; reasoning changes do
not. Validate with the smallest ADW before using a new roster. See
[references/config.md](../references/config.md).

Only `phase_seconds` is currently enforced by the runtime. Treat
`tool_seconds` and `correction_seconds` as reserved fields, not independent
tool or correction limits.
