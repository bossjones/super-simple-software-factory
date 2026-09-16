---
name: sssf
description: Install and operate SSSF when creating, running, updating, or observing deterministic AI developer workflows and their agent roster.
compatibility: Requires Python 3.11+, uv, git, sqlite3, and GitHub Copilot authentication. Bun is optional for the visualizer.
metadata:
  author: bossjones
  version: "1.0.0"
---

# Super Simple Software Factory

SSSF combines deterministic Python ADWs with bounded GitHub Copilot agent
sessions. ADWs own sequencing, retries, gates, permissions, evidence, and
acceptance. Copilot proposes; deterministic code disposes.

## Startup

Read [cookbooks/sssf_overview.md](cookbooks/sssf_overview.md). If this is an
installation request, load [cookbooks/install.md](cookbooks/install.md).
Otherwise route the request through the table below and load only the
referenced cookbook.

| Request | Cookbook |
|---|---|
| install the factory | [cookbooks/install.md](cookbooks/install.md) |
| create an ADW | [cookbooks/create_adw.md](cookbooks/create_adw.md) |
| change an ADW chain | [cookbooks/update_adw.md](cookbooks/update_adw.md) |
| create the roster | [cookbooks/create_config.md](cookbooks/create_config.md) |
| tune an agent | [cookbooks/update_config.md](cookbooks/update_config.md) |
| extend deterministic modules | [cookbooks/update_modules.md](cookbooks/update_modules.md) |
| turn a request into an ADW prompt | [cookbooks/how_to_prompt_for_the_eng.md](cookbooks/how_to_prompt_for_the_eng.md) |
| run or observe an ADW | [cookbooks/run_adw.md](cookbooks/run_adw.md) |

Deep contracts are lazy-loaded from
[references/config.md](references/config.md),
[references/handoff.md](references/handoff.md), and
[references/observability.md](references/observability.md).

## Non-negotiable operating rules

1. Validate the roster and Copilot SDK/runtime before an agent phase starts.
2. Give every agent call a concrete typed envelope and a matching JSON report.
3. Keep malformed-output and gate corrections in the same Copilot session.
4. Use deterministic code phases for known commands, tests, commits, and
   migrations.
5. Treat post-send `writes` and protected-path enforcement as the authoritative
   repository boundary. `available_tools` narrows capabilities; the
   approve-once callback does not enforce path policy before execution.
6. Subscribe to Copilot events during session creation/resume; redact and
   normalize them before they enter raw JSONL or the SSSF trace.
7. Treat `session.idle` as mechanical completion. A wait timeout is not an
   abort; call `session.abort()` on a deadline.
8. Disconnect to preserve resumable state. Never silently create a replacement
   after resume failure.
9. End every ADW with `run.finish(accepted=...)`.
10. Never place credentials in prompts, checked-in configuration, subprocess
    arguments, or raw/SQLite traces. A local ignored `.env` may hold one
    supported token when CLI login is unavailable.

## Canonical package layout

The plugin root contains `plugin.json` and the canonical skill at
`skills/sssf/SKILL.md`. Its scripts, cookbooks, references, and templates are
all relative to `skills/sssf/`. A tracked symlink at `.agents/skills/sssf`
exposes the same directory as a project skill in a plain checkout of the
plugin repository. In a stamped target repository, generated
runtime files live under `adws/` and runtime state under
`adws/adw_data/`.

## Copilot-first operation

For local plugin development use:

```bash
copilot --no-auto-update --plugin-dir . plugin list
```

The plugin listing is the required discovery check. `skill list --json` is
optional and version-dependent; a plugin-provided skill may not appear there.
The official Python SDK is the only agent execution integration. Use
`copilot --version`, then run both SDK checks with the pinned package:

```bash
copilot --version
uv run --with github-copilot-sdk==1.0.13 python -c \
  "import importlib.metadata as m; print(m.version('github-copilot-sdk'))"
uv run --with github-copilot-sdk==1.0.13 python -m copilot download-runtime
```

Read the official
[Python SDK README](https://github.com/github/copilot-sdk/blob/main/python/README.md)
when lifecycle behavior is version-sensitive.

The [Agent Skills specification](https://agentskills.io/specification),
[Copilot plugin documentation](https://docs.github.com/en/copilot/concepts/agents/about-plugins),
and [MCP documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers)
define packaging and tool-extension behavior. These controls complement, but
do not replace, SSSF's deterministic write-policy enforcement.
