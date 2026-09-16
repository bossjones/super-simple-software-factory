# Audit the operator docs for stale or unfulfilled notes

Read-only. Find every sentence in the user-facing SSSF documentation that
describes work as in progress, refers to something that does not exist in
this checkout, or carries a date that is older than the newest commit.

Search these paths and nothing else:

- `README.md`
- `docs/*.md`
- `skills/sssf/SKILL.md`
- `skills/sssf/cookbooks/*.md`
- `skills/sssf/references/*.md`
- `skills/sssf/templates/justfile`
- `ai_docs/*.md` (skip any file containing `historical: true`)

For each hit, record the file, the sentence, and one line on why it is stale
or unfulfilled. Write the full list to `<context_handoff_dir>/scout_findings.md`.
Change nothing in the repository.

Done means the findings file exists and every `findings[].file` in your report
is a path that exists in this checkout.
