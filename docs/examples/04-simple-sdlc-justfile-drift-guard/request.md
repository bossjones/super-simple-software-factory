# Guard the stamped justfile against referencing scripts that are not stamped

Every `just` recipe in `skills/sssf/templates/justfile` that runs
`uv run adws/adw_<name>.py` assumes `install.py` stamps that script. Nothing
checks this today: a recipe could name an ADW that was renamed or removed,
and a fresh target would only find out at run time.

Add a deterministic test in `tests/test_plugin_layout.py`:

- Parse `skills/sssf/templates/justfile` for every `adws/adw_*.py` path.
- Assert each one exists under `skills/sssf/templates/adws/`.
- Assert the reverse too: every `skills/sssf/templates/adws/adw_*.py` that is
  not a module under `adw_modules/` is referenced by at least one recipe, or
  is listed in an explicit `UNRECIPED_ADWS` allowlist in the test with a
  one-line reason each.

Constraints: touch only `tests/test_plugin_layout.py`. If the reverse check
finds real drift, list those ADWs in the allowlist with the reason rather than
editing the justfile; that is a separate request.

Done means `uv run pytest -q tests/test_plugin_layout.py` passes, and
deleting any `adws/adw_*.py` line from the template justfile makes the new
test fail.
