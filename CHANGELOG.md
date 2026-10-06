# Changelog

## 0.1.1 — 2026-10-06

- Omit opaque binary app-state fields from flight JSON to support the installed Flighty schema.
- Add a regression test for binary fields in list, detail, and status results.
- Verify read commands and creation preview against a real local Flighty database without writing to it.

## 0.1.0 — 2026-10-06

- Initial public package: deterministic Python CLI and Flighty agent skill.
- Local flight queries, friend filters, status, forecasts, catalogs, statistics, and connections.
- Flight creation previews, explicit timestamps, mandatory write backups, and duplicate detection.
- JSON output, repeatable clock option, synthetic integration tests, and Python wheel packaging.
