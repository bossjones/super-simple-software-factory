# Run and observe an ADW

Read [how_to_prompt_for_the_eng.md](how_to_prompt_for_the_eng.md), then run
from the target repository root:

```bash
uv run adws/adw_simple_sdlc.py "implement the requested change"
uv run adws/adw_plan_build.py request.md --adw-id a1b2c3d4
```

Use `--config` to select a roster and `--adw-id` to join a session. A joined
run reuses each agent's recorded Copilot session when the model is unchanged.

Observe the same trace the visualizer reads:

```bash
just sessions
just phases a1b2c3d4
just procs a1b2c3d4
```

`sssf.db` is WAL-enabled and can be read while a run writes. Raw Copilot
events, prompts, envelopes, and `agent_map.json` live under
`adws/adw_data/sessions/a1b2c3d4/`. Do not edit them by hand.

If a run is stuck, inspect the process rows and use the repository's kill
helper. A timeout aborts active Copilot work before cleanup; a failed resume is
reported rather than replaced.
