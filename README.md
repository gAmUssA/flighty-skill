# Flighty skill + CLI

A Tessl plugin with a bundled Python 3.11+ CLI for local Flighty data. Queries, filtering, statistics, status calculations, and flight creation run in code. The agent skill translates user requests and explains JSON results. No MCP server, Python runtime dependencies, API keys, or network calls are required.

Inspired by [LukasHaas/flighty-mcp](https://github.com/LukasHaas/flighty-mcp), with an independently implemented CLI against its documented SQLite table relationships. This repository does not modify or contribute to the upstream project.

## Skill triggers

The skill activates for requests about your local Flighty data, such as:

- "What are my upcoming flights?"
- "Show my Flighty stats for 2025."
- "What flights does Felix have coming up?"
- "What is the status or delay forecast for my UA194 flight?"
- "Find airports in Zurich" or "show my Flighty connections."
- "Add this flight to Flighty."

It supports explicit invocation as `flighty` in agents that expose named skills. It reads cached local data rather than searching global live schedules.

## Run

```bash
python3 skills/flighty/scripts/flighty.py --help
python3 skills/flighty/scripts/flighty.py list --upcoming
python3 skills/flighty/scripts/flighty.py stats --year 2025 --past
```

Alternatively, `pip install .` provides `flighty`. Default database:
`~/Library/Containers/com.flightyapp.flighty/Data/Documents/MainFlightyDatabase.db`.
Use `FLIGHTY_DB_PATH` or `--db PATH` for a copy or another location. `doctor` lists active user IDs; set `--user-id` when needed. Live use requires macOS with Flighty installed and filesystem permission to access its data. Tests use synthetic SQLite files and run without Flighty.

The CLI covers the upstream tool families: personal flights, friends, detail lookup, search, status, forecasts, airports, airlines, stats, connections, and add. JSON success goes to stdout; JSON failures go to stderr with exit 1. Help/version emit text. Read results come from the local cache. `--now` pins time; date-only filters use UTC and `--date` flight lookup uses departure-airport local time.

## Tessl package

Plugin identity: `gamussa/flighty`, version `0.1.1`. The manifest is `.tessl-plugin/plugin.json`; Tessl generates legacy `tile.json` metadata inside the archive. The CLI ships inside the skill so installation preserves its relative path. The namespace is a packaging default; publishing requires access to that Tessl workspace.

```bash
tessl plugin lint .
tessl skill lint .
tessl plugin pack . --output dist/flighty-0.1.1.tgz
```

See `tessl install --help` for local archive installation supported by your CLI. After registry publication, consumers can use `tessl install gamussa/flighty`. Packaging does not publish the plugin.

Once the public GitHub repository is available, the skill can also be installed with:

```bash
tessl install github:gAmUssA/flighty-skill --skill flighty
```

## Creation

`add` previews by default. Provide both airports and full departure/arrival timestamps with explicit UTC offsets; times and routes are never estimated. Authorized writes additionally require `--write --backup PATH`. Inserts are atomic and duplicate-aware. Cloud synchronization is not verified. This differs from upstream's optional AirLabs lookup and estimated times.

See [the command reference](skills/flighty/references/commands.md) for examples and behavior.

## Validate

```bash
python3 -m unittest discover -s tests -v
tessl skill lint .
```

No personal flight data is included in this package. Tests cover scope isolation, pagination, dates, schema variations, binary fields, calculations, backups, duplicate detection, and rollback. Read commands and creation preview were also verified against a real local Flighty database. Writes and cloud synchronization remain unverified against the live app.
