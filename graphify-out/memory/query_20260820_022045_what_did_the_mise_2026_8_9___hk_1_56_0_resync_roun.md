---
type: "query"
date: "2026-08-20T02:20:45.603526+00:00"
question: "What did the mise 2026.8.9 + hk 1.56.0 resync round actually deliver?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the mise 2026.8.9 + hk 1.56.0 resync round actually deliver?

## Answer

# Round 2026-08-19e — mise 2026.8.9 + hk 1.56.0 resync, and what running things taught

## What shipped into the working tree (this repo)

- `mise` 2026.8.9 and `hk` 1.56.0 across every place each version is written.
  Ray ruled `min_version = { hard = "2026.8.9", soft = "2026.8.9" }`, overriding
  `mise.toml`'s own comment; the comment was rewritten in the same change so the
  file no longer argues against its values, and `soft` is documented as
  intentionally inert.
- `sources/mise.manifest` was pinning a **tag object**, not a commit. Control
  arm: `gh api repos/jdx/hk/commits/v1.55.0` reproduced hk's pin byte-for-byte
  while the same call for mise disagreed with the manifest. mise ships annotated
  tags, hk lightweight ones. The `git ls-remote --tags` instruction that caused
  it was rewritten in BOTH manifests.
- **Two `ref_binding` entries for `hk.pkl`** in `currency.toml`. The mechanism
  already existed (graphify declares eight); hk declared none, so the check
  reported `ref-binding | skip | this tool declares no revision bindings` — a
  SKIP whose stated reason was a true fact about the repo. It cost a live
  defect: the 1.55.0 bump moved the pin and the manifest and left `hk.pkl` on
  **v1.54.1**. Armed three ways (clean / `amends` stale / `import` stale).
- **`timeout` on 7 tasks, up from 0 of 75.** `long-running-command-hangs.md`
  rule 1 has named this mechanism since it was written — the answer to the
  7-hour hk wedge — and the repo had never adopted it.
- **`ruff_format` declared last.** `exclusive` is a whole-pipeline barrier; at
  position 15 of 20 it split the run into three phases and stranded five
  unrelated steps behind a 40 ms task.
- **`hk-test` is a gate**: `[tasks.hk-test]` -> `kb_setup.hk_test`, added to
  `GATE_TASKS`, deliberately NOT in `CONCURRENT_SAFE`. Two counts travel with
  this and are easy to swap: the gate RUNS hk's **46** step-defined tests (what
  `CLAUDE.md` quotes and what the floor of 40 sits under), while the wrapper
  module carries pytest unit tests OF ITS OWN — 11 at `d3c381139f2b`, 15 after
  the cold-review fixes. Neither number is the other; the second one moves
  whenever the module gains a test, so read it from the suite, not from here.
- **`lint` now emits structured output**: `HK_TIMING_JSON` + `HK_OUTPUT_FILE`
  into `.agent/kb/gates/`, armed both directions, human stdout unchanged.

## What shipped into `~/.config/mise` (chezmoi render — see CHANGES-2026-08-19.md)

`lockfile = true` + a 119-tool lockfile; `brew upgrade --yes`; `wait_for` so
brew precedes mise; the `-- --system -y` flag bug fixed; `update:claude`
rewritten in Python with a thread pool; a new read-only `update:check`;
`update:all` as the single entry point. A stale `context7-plugin` registration
was uninstalled. End state measured: 225 targets, 0 failed, 57.8s, exit 0 —
down from 211s and exit 1.

## The through-line

Almost everything of value this round came from RUNNING something, not reading
it. The resync itself was the small part; five live runs of one task each found
a defect that reasoning had not.


## Outcome

- Signal: useful