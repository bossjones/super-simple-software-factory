# Create an ADW

Design the chain before writing it:

1. Name the Copilot agents and their order.
2. Put known commands in deterministic code phases.
3. Select a typed envelope and gates for every agent call.
4. Bound correction and fix loops.

Generate a starter:

```bash
uv run skills/sssf/scripts/make_adw.py --name review_docs --agents scout,builder
```

Every ADW validates its roster first, records the engineer request, and uses
`previous=` for typed handoffs:

```python
agents.validate(cfg, REQUIRED_AGENTS)
run = session.ensure(cfg, adw_id)
with run.phase(PhaseParams(name="build", kind="agent", owner="builder",
                           description="Implement the requested change")) as ph:
    build = ph.call(AgentCall(output_type=BuildOutput, prompt=prompt,
                              previous=plan,
                              gates=[gates.diff_matches_claims]))
return run.finish(accepted=build.status == "success")
```

Keep scripts thin. Runtime lifecycle, parsing, permissions, tracing, and
reusable predicates belong in `adw_modules/`.
