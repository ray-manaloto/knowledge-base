# Lane: refute-uv-tree-json-gate (2026-08-18)

Target finding: "directive gate-2 command `uv tree --outdated --show-sizes --all-groups --format json`
emits zero 'latest' annotations (JSON drops outdated data) -> gate green forever; text form shows 4
top-level stale (graphifyy 0.9.45->0.9.46, datamodel-code-generator 0.72.4->0.74.0, ruff 0.16.2->0.16.3,
ty 0.0.69->0.0.72)."

Job: refute if possible. Prime suspect: token-spelling bound — grep '"latest"' does NOT match a key
like "latest_version"; must enumerate the JSON's actual key set.

## Findings (as I go)

(in progress)
