# Running the visualizer

The visualizer is a read-only observability UI over a target repository's
`adws/adw_data/sssf.db`. It lives in this checkout at
[`skills/sssf/apps/visualizer/`](../skills/sssf/apps/visualizer/) and is
never stamped into a target. You run it from the SSSF checkout and point it at
whichever database you want to look at.

It has two parts:

- **Server** ([`server/index.ts`](../skills/sssf/apps/visualizer/server/index.ts)):
  a Bun process that serves a JSON API over the database and, when a `dist/`
  build exists, the built UI. Default port 4600.
- **UI** ([`src/`](../skills/sssf/apps/visualizer/src/)): a Vue app. In dev
  mode Vite serves it on port 4601 and proxies `/api` to the server.

There is no ingest endpoint and no websocket. ADWs write to SQLite; the UI
polls the same tables `just sessions`, `just phases`, and `just tail` query.

## Prerequisites

- [Bun](https://bun.sh/). `just doctor` reports whether it is installed.
- A trace database. `just demo` in any stamped target creates one at
  `adws/adw_data/sssf.db`.

Install dependencies once:

```bash
just visualizer-install
```

## Option A: one process (simplest)

Build the UI, then serve API and UI together on port 4600:

```bash
just visualizer /path/to/target/adws/adw_data/sssf.db
```

Open `http://localhost:4600`. This is the right choice when you just want to
look at a run. Rebuilding is only needed when the visualizer source changes.

## Option B: two processes (developing the UI)

Terminal 1, the API server:

```bash
just visualizer-server /path/to/target/adws/adw_data/sssf.db
```

Terminal 2, the Vite dev server with hot reload:

```bash
just visualizer-dev
```

Open the URL Vite prints, `http://localhost:4601` by default. The dev server
proxies every `/api` request to port 4600, so the server must be running
first.

## Pointing at a database

The server resolves the database path in this order:

| Source | Example |
|---|---|
| `--db` flag | `bun run server/index.ts --db /abs/path/sssf.db` |
| `--db=` inline | `bun run server/index.ts --db=/abs/path/sssf.db` |
| `SSSF_DB` environment variable | `SSSF_DB=/abs/path/sssf.db bun run server/index.ts` |
| default | `adws/adw_data/sssf.db` relative to the current directory |

The `just visualizer` and `just visualizer-server` recipes convert the path
you pass into an absolute path before changing into the visualizer directory,
so a relative path from the checkout root works. Override the port with
`PORT=4700 just visualizer-server ...`; the Vite proxy reads the same
variable.

The server refuses to start if the database does not exist or cannot be
opened, and prints why.

## What the server reads and writes

Every query runs on a read-only connection, so a running ADW is never
blocked. The server also holds one ordinary connection open for its lifetime
and never executes a statement on it beyond a journal-mode pragma. That
connection exists because SQLite deletes a WAL database's `-wal` and `-shm`
sidecar files when the last writer closes, and a read-only connection cannot
recreate them; without it, a finished run's database could not be opened.
The single write is `POST /api/sessions/:adw_id/archive`, which sets the
`archived` flag on one row of `sessions` when you click "archive" in the UI.
Runs never set that flag.

Prompts shown in the phase detail view are read from the session directory
next to the database, `adws/adw_data/sessions/<adw_id>/<agent>/prompts/`.
Both path segments must match `[A-Za-z0-9._-]+`; anything else is rejected
rather than sanitized.

## JSON API

Every route returns JSON with `cache-control: no-store`.

| Route | Returns |
|---|---|
| `GET /api/health` | `{ok, db, journal_mode, sessions}` |
| `GET /api/sessions?limit=200` | Recent session rows with phase and agent summaries |
| `GET /api/sessions/:adw_id` | One session with its phases |
| `GET /api/sessions/:adw_id/events?after=<rowid>&limit=<n>` | Normalized events, cursor-paged by rowid |
| `GET /api/sessions/:adw_id/envelopes` | Every typed envelope the run recorded |
| `GET /api/sessions/:adw_id/gates` | Gate results with their `{item, ok, note}` checks |
| `GET /api/sessions/:adw_id/agents/:agent/prompts` | The rendered system and user prompts |
| `POST /api/sessions/:adw_id/archive` | Sets the archive flag; the only write |

A quick check that the server is up and sees your data:

```bash
curl -s http://localhost:4600/api/health
```

## What the screens show

- **Session list**: one card per run with status, request, per-agent
  timeline, phase dots, tokens, cost, and duration.
- **Trace view**: the run as ordered lanes for engineer, code, and each
  agent, with phase durations and context-window occupancy.
- **Phase detail**: for agent phases, the recorded model, reasoning effort,
  tools, Copilot session ID, SDK/runtime/protocol/CLI versions, the envelope,
  and every gate check.

Screenshots of each screen are in [tutorial.md](tutorial.md#9-run-the-visualizer-from-your-sssf-checkout).

## Build and lint checks

`just visualizer-build` is what `just verify` and CI run. It installs with
`--frozen-lockfile`, type-checks with `vue-tsc`, and builds with Vite. It does
not start a server. Inside the visualizer directory, `bun run lint` runs
oxlint and `bun run typecheck` runs the type check alone.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `bun: command not found` | Bun is not installed | Install from [bun.sh](https://bun.sh/), or skip the visualizer; every `just` observation recipe works without it |
| Server exits immediately naming the database | The path does not exist or is not a SQLite file | Run `just demo` in the target first, then pass the absolute path to `adws/adw_data/sssf.db` |
| UI loads but shows no sessions | The server is reading a different database than you expect | `curl -s localhost:4600/api/health` and check the `db` field |
| `/api` requests fail in dev mode | The Vite dev server is up but the API server is not | Start `just visualizer-server ...` first, then `just visualizer-dev` |
| Port already in use | A previous server is still running | Stop it, or set `PORT` for both the server and Vite |
| Prompts panel is empty for a phase | The session directory is not beside the database, or the run predates prompt capture | Check `adws/adw_data/sessions/<adw_id>/<agent>/prompts/` exists in the target |
