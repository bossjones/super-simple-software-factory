# Plan: detect the test command at install time

Today `skills/sssf/scripts/install.py` stamps `adws/adw_modules/quality.py`
with every quality block pointing at `_placeholder(...)`, an `echo` that
passes. A new user who runs `just sdlc` gets a green test phase that tested
nothing until they hand-edit the file.

Plan only. Do not implement.

Propose how `install.py` should pre-fill the `test` argv when the target
repository makes the answer obvious, and leave the placeholder otherwise:

- `pyproject.toml` with a `[tool.pytest.ini_options]` table, or a `pytest`
  dependency, means `["uv", "run", "pytest", "-q"]`.
- `package.json` with a `test` script means `["bun", "run", "test"]` when
  `bun.lock` exists, otherwise `["npm", "test"]`.
- Anything else keeps the placeholder and the installer prints a reminder.

The plan must name the files to touch (installer, template, tests under
`tests/test_install.py`), how the detection is unit-tested with fixture
directories, and how a user overrides the guess. It must not propose reading
any file outside the target repository root.

Write the plan to `<context_handoff_dir>/plan.md` and copy it to
`specs/<adw_id>_quality_argv_detection.md`. Done means both files exist and
the plan lists at least one test per detection branch.
