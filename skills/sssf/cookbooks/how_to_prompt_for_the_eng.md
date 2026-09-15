# Write the engineer prompt

The engineer prompt is passed through the ADW and becomes context for one or
more Copilot sessions. Make it precise:

- state the desired outcome and affected paths;
- identify constraints and protected files;
- distinguish investigation from edits;
- name the verification command;
- define “done” with observable evidence.

Good:

```text
Update the user-facing SSSF docs to describe Copilot CLI plugin validation and
the Python SDK preflight. Change only README.md and skills/sssf Markdown files.
Done means the stale path search is empty and docs-check passes.
```

Avoid asking an agent to run a command that deterministic code already knows,
or to report success without naming artifacts and evidence. The agent returns
the exact typed JSON requested by its prompt; prose belongs in handoff files.
