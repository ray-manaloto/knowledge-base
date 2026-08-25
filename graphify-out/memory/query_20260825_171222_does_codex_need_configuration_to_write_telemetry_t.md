---
type: "query"
date: "2026-08-25T17:12:22.467317+00:00"
question: "Does codex need configuration to write telemetry to disk for parsing?"
contributor: "graphify"
outcome: "corrected"
correction: "Do not plan \"configure codex to write telemetry to disk\" before reading the\nschema's exporter enum. The task was framed as a configuration job and is\nactually a PARSING job: the JSONL rollouts have been accumulating all along.\n\nThe generalisable rule: when a task is phrased as \"make tool X emit Y\", check\nwhether X already emits Y somewhere you have not looked, BEFORE reading how to\nconfigure it. A directory listing (`ls ~/.codex/`) settled in one command what\nthe 181KB schema could not, because the schema describes what is CONFIGURABLE\nand says nothing about what is already DEFAULT behaviour.\n"
---

# Q: Does codex need configuration to write telemetry to disk for parsing?

## Answer

Codex CAN be configured for telemetry, but not to a file. `OtelExporterKind` in
the rust-v0.149.1 `config-schema.json` is `oneOf`: `none` | `statsig` |
`otlp-http {endpoint, protocol, headers, tls}` | `otlp-grpc {endpoint, ...}`.
There is no file exporter, so OTEL requires a collector listening on an endpoint.

The disk telemetry we wanted already exists WITHOUT any configuration:
`~/.codex/sessions/` holds 2,359 `.jsonl` rollout files, date-partitioned
`YYYY/MM/DD/rollout-<ISO-ts>-<uuid>.jsonl` (extension tally: 2,359 of 2,359 are
jsonl), plus `~/.codex/archived_sessions/`, `history.jsonl`, `session_index.jsonl`.
`~/.codex/otel/` even holds a pre-scaffolded collector.

The config keys that govern disk output are `history` (persistence, max_bytes)
and `log_dir` — NOT `otel`.


## Outcome

- Signal: corrected
- Correction: Do not plan "configure codex to write telemetry to disk" before reading the
schema's exporter enum. The task was framed as a configuration job and is
actually a PARSING job: the JSONL rollouts have been accumulating all along.

The generalisable rule: when a task is phrased as "make tool X emit Y", check
whether X already emits Y somewhere you have not looked, BEFORE reading how to
configure it. A directory listing (`ls ~/.codex/`) settled in one command what
the 181KB schema could not, because the schema describes what is CONFIGURABLE
and says nothing about what is already DEFAULT behaviour.
