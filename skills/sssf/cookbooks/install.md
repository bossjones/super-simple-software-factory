# Install

## Plugin discovery

Install from the plugin marketplace when available. This makes the skill
discoverable to Copilot; it does not stamp a target repository or provide the
installer path there:

```bash
copilot plugin install bossjones/super-simple-software-factory
```

The required discovery evidence is:

```bash
copilot plugin list
```

`copilot skill list` is optional and version-dependent. A plugin-provided skill
may not appear in that output.

## Stamp a target repository

Locate or clone a separate SSSF checkout:

```bash
git clone https://github.com/bossjones/super-simple-software-factory.git \
  "$HOME/src/super-simple-software-factory"
```

Run its installer from the target repository root:

```bash
uv run "$HOME/src/super-simple-software-factory/skills/sssf/scripts/install.py"
```

When the target is the checkout itself, use the relative path:

```bash
uv run skills/sssf/scripts/install.py
```

For local plugin development, validate the separate checkout without
installing it:

```bash
copilot --no-auto-update --plugin-dir /path/to/super-simple-software-factory plugin list
```

The installer creates `adws/`, `.env.sample`, `justfile`, and prompt/runtime
templates, and adds the target-repository ignore rules. Session and trace
directories are created on the first ADW run. Existing files are skipped. Use
`--force` only after backing up local configuration; it overwrites stamped
files.

## Preflight

Install/authenticate the prerequisites, then check the SDK/runtime:

```bash
copilot login
copilot --version
uv run --with github-copilot-sdk==1.0.13 python -c \
  "import importlib.metadata as m; print(m.version('github-copilot-sdk'))"
uv run --with github-copilot-sdk==1.0.13 python -m copilot download-runtime
```

CLI login is preferred. The local ignored `.env` is also an accepted token
store for the variables in `.env.sample`; never commit `.env` or put tokens in
prompts or CLI arguments.
Python 3.11+, `uv`, Git, `sqlite3`, and `just` are required; Bun is optional.

## Smoke test

```bash
just demo
just sessions
```

The stamped target's supported observation commands are `just sessions`,
`just phases <adw_id>`, `just tail <adw_id>`, and `just procs <adw_id>`. The
installer does not stamp the optional visualizer, so there is no target-local
visualizer command to document here. If the smoke test fails, inspect the
phase and trace before composing a multi-agent chain.
