# Add the `kill` recipe the run cookbook already promises

`skills/sssf/cookbooks/run_adw.md` tells an operator with a stuck run to
"use the repository's kill helper", but the stamped
`skills/sssf/templates/justfile` has no such recipe. Close the gap.

Add a `kill ADW_ID` recipe to `skills/sssf/templates/justfile` under the
"watch it" section that:

1. Queries the `processes` table for rows with that `adw_id` and
   `ended_at is null`, exactly like the existing `procs` recipe.
2. For each row, prints the recorded `pid` and `command`, then checks with
   `ps -p <pid> -o command=` that the live process matches the recorded
   command before sending `SIGTERM`. A pid whose command differs is skipped
   with a message; a recycled pid must never be killed.
3. Prints how many processes were signalled and reminds the operator that the
   runtime aborts active Copilot work on its own deadline.

Then update `skills/sssf/cookbooks/run_adw.md` so the sentence names
`just kill <adw_id>` instead of "the repository's kill helper".

Constraints: touch only those two files. Do not add a new script. Keep the
recipe POSIX-shell portable (it runs under `just`'s default `sh`).

Done means `just --list` in a freshly stamped target shows `kill`, the recipe
refuses to signal a pid whose command does not match, and the cookbook links
the recipe by name.
