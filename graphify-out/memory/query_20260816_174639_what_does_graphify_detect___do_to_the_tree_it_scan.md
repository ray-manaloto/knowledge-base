---
type: "query"
date: "2026-08-16T17:46:39.174377+00:00"
question: "What does graphify detect() do to the tree it scans, and does a pin guarantee what runs?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does graphify detect() do to the tree it scans, and does a pin guarantee what runs?

## Answer

graphify's `detect()` WRITES INTO THE TREE IT SCANS — and the version pin is not what reaches your shell.

Two corpus facts from clearing #289, both of which cost real time to find and
neither of which is in any doc.

**1. `detect()` is not read-only.** Given an Office or Google-Workspace document
under the scan root, it converts it and writes the markdown sidecar to
`<root>/graphify-out/converted/`. That path is HARDCODED in `detect.py`
(`converted_dir = root / GRAPHIFY_OUT / "converted"`); `cache_root` reads like the
knob for it but only reaches the word-count cache. `cognee` ships `example.docx`
and `example.pptx`, so it alone failed this repo's post-detection cleanliness
assertion — reported for two rounds as a "snapshot drift RACE" when it is fully
deterministic. Filed upstream as Graphify-Labs/graphify#2787.

Consequence for this repo: the cleanliness check now ignores UNTRACKED entries
under `graphify-out/` only. A modified or deleted tracked file there is still
drift — the invariant is that the detector never alters your CONTENT, and adding
its own output is a different thing from changing yours.

**2. graphify's partial-extraction warning cites a CLOSED, unrelated issue.**
`extract.py:5636` hardcodes `(#2551)` for every language; #2551 is a closed
KOTLIN issue, and their own comment at 5619 calls it "the genuine #2551 Kotlin
one-line-body" case while still emitting it for everything. I recorded an
`.astro` failure as "already tracked upstream" on the strength of that number and
only found otherwise by opening it. **A citation inside a tool's own message is a
secondary source and ages like any other** — open it before repeating it. Filed
as Graphify-Labs/graphify#2788.

**3. `uv run <tool>` can reach an UNPINNED ambient install.** The
`datamodel-codegen` version check failed against its 0.72.4 pin. The previous
handoff diagnosed ".venv drift, cured by uv sync" — wrong. `uv sync --locked`
reports everything satisfied and the binary is still 0.73.0, because `codegen` is
an OPTIONAL group (never installed by default, so `.venv/bin` has no such binary)
and a `pipx-datamodel-code-generator` 0.73.0 sits on PATH that NOTHING pins —
absent from `mise.toml` and `currency.toml` both. `uv sync --locked --group
codegen` fixes the host; #329 tracks the real fix. `uv run` is not a guarantee
that a pin is what executes.


## Outcome

- Signal: useful