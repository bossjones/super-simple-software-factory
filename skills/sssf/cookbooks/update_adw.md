# Update an ADW

Add or remove phases without moving deterministic responsibilities into
prompts. Use `kind="agent"` for Copilot work and `kind="code"` for known
commands. Every phase has a unique name and an earned description.

Gate corrections are bounded and stay in the same session:

```python
with run.phase(PhaseParams(name="review", kind="agent", owner="reviewer",
                           retries=1,
                           description="Confirm the change meets the request")) as ph:
    review = ph.call(AgentCall(output_type=ReviewOutput, prompt=prompt,
                               previous=build,
                               gates=[gates.verdict_consistent]))
```

Malformed JSON uses the same-session correction budget separately from gate
retries. A failing test is evidence for a bounded builder-fix loop, not a
tester agent. Finish the run with an explicit acceptance condition.
