# Detect the test command at install time

## Files to touch

- `skills/sssf/scripts/install.py`: add `detect_test_argv(root: Path) -> list[str] | None`
  and call it after `quality.py` is stamped. Add a `--no-detect` flag.
- `skills/sssf/templates/adws/adw_modules/quality.py`: replace the bare
  `_placeholder("test")` call with a marker line the installer can rewrite:
  `argv=_placeholder("test"),  # sssf:test-argv`.
- `tests/test_install.py`: one test per branch below, each stamping into a
  `tmp_path` fixture directory.

## Detection rules

| Evidence at target root | argv |
|---|---|
| `pyproject.toml` containing `[tool.pytest.ini_options]` or a `pytest` dependency | `["uv", "run", "pytest", "-q"]` |
| `package.json` with a `test` script and `bun.lock` present | `["bun", "run", "test"]` |
| `package.json` with a `test` script and no `bun.lock` | `["npm", "test"]` |
| none of the above | keep the placeholder; print `test command not detected; edit adws/adw_modules/quality.py` |

## Tests

- `test_detects_pytest_from_ini_options`
- `test_detects_pytest_from_dependency`
- `test_detects_bun_test_script`
- `test_detects_npm_test_script`
- `test_keeps_placeholder_when_nothing_matches`
- `test_no_detect_flag_keeps_placeholder`
- `test_rerun_does_not_rewrite_an_edited_quality_py` (idempotence)

## Override

`--no-detect` skips the rewrite. A user can always edit `quality.py` by hand;
the rewrite only happens on first stamp, never on a skipped file.

## Verification

`uv run pytest -q tests/test_install.py`, then `just verify`.
