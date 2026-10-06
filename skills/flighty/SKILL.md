---
name: flighty
description: Query the local Flighty macOS database for personal or friends' flights, status, delay forecasts, airport or airline searches, statistics, and connections; preview or add a flight using the bundled CLI. Use for requests such as "my upcoming flights", "my Flighty stats", or "add this flight to Flighty". Requires a local Flighty database; does not search global live flight schedules.
---

# Flighty

Process steps in order. Do not skip ahead.

## Step 1 — Locate the CLI

Use Python 3.11+ with `scripts/flighty.py` resolved relative to this SKILL.md. In a Tessl project installation the command is:

```bash
python3 .tessl/plugins/gamussa/flighty/skills/flighty/scripts/flighty.py --help
```

For a user-wide or differently mounted plugin, use its actual absolute script path. No installation or MCP server is needed. An installed Python package also exposes `flighty`.

## Step 2 — Select the operation

Read [references/commands.md](references/commands.md) for arguments and examples. Invoke the CLI rather than generating SQL or reimplementing calculations. Translate the request into explicit filters and dates; clarify missing details only when they affect the result. Global options precede the subcommand. Default scope is the owner; select friends or all only when requested. Use `doctor` when database access or owner inference needs diagnosis, and `--user-id` when inference is ambiguous or the user specifies an account.

For "next flight", use `list --upcoming --limit 1`; for historical statistics use `stats --year YYYY`. Use full flight codes, and specify `--date` or `--id` to disambiguate repeated services. An omitted date selects the most recent scheduled matching instance, which may be a future flight. Paginate when the request requires more than one page. Choose airport IATA codes when known.

## Step 3 — Execute the CLI

Success writes one JSON envelope `{ok:true, command, data}` to stdout and exits 0. Failures exit 1 and write `{ok:false,error}` to stderr. Help and version are plain text. Empty results are valid; do not invent flights or missing values. Handle errors using the stated diagnostic without editing Flighty's schema or bypassing filesystem access restrictions.

For creation, obtain the full flight code, both airport codes, and explicit departure and arrival ISO datetimes with UTC offsets, including the arrival date. Do not guess times, routes, offsets, or date rollover. `add` previews by default. When the user has authorized adding the flight, execute the same inputs with `--write --backup PATH`, choosing a new backup path outside the plugin. A preview alone does not mean the flight was saved. The CLI performs a local database write; Flighty cloud synchronization is not verified. See the command reference for its write contract.

## Step 4 — Explain the result

Summarize the relevant returned fields. Dates are UTC unless otherwise stated; use returned airport timezone identifiers to present local times and label the zone. Status and delay forecasts reflect Flighty's local cache, not a fresh network lookup. Missing values mean unavailable data. A below-minimum connection is a calculated flag, not a guarantee about making the flight. Report whether an add was previewed, created, or already present, and include the backup path after a successful write.
