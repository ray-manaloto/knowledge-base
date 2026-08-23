# Refute lane: finding 14 (kb-validate-chunks has no line-anchor check)

Claim under test: `mise run kb-validate-chunks` (`chunks._node_issues`) checks
`source_location` SHAPE but never checks the line number against the referenced
source file, so a +11 anchor offset had to be repaired by hand.

## Reads so far (primary artifact)

- `python/src/kb_setup/chunks.py:146-190` `_node_issues` — checks: dict-ness, id,
  `_NODE_REQUIRED` presence, `captured_at` regex, `source_file` ABSOLUTE-ness,
  `_origin == "semantic"`. No file open, no line number.
- `grep -n source_location python/src/kb_setup/chunks.py` -> 80, 83, 90, 96, 186 —
  **all five are comment/message TEXT**, never `n.get("source_location")`.
  Control arm in same file: `source_file` IS read as a key at line ~171
  (`sf = n.get("source_file")`), so the grep discriminates key-reads from prose.
- `mise.toml:1245-1246` description = 'Schema + edge-direction check on extraction
  chunks: ...' — matches the finding's quote.
- `python/src/kb_setup/cli.py:838-872` `_validate_chunks` = validate_files +
  collision_issues + _report_edge_direction. No anchor check in the task path.
- A line-count helper DOES exist elsewhere: `resolve.line_count` (resolve.py:660),
  used by `handoff.py:289` / citations — i.e. the capability exists in the repo
  but is not wired to chunk validation.

## NUANCE / possible defect in the finding's wording
`_node_issues` does NOT "check source_location SHAPE". It checks `_origin`
explicitly *so that graphify's shape fallback is never consulted*. The
shape-vs-AST discussion is in the module comment (lines 74-102), not in code.

## The empirical arms (the decisive probe)

Built from the committed `sources/extractions/dotfiles-secrets-docs.json`
(node0 `source_file=sources/media/dotfiles-secrets-guide.md`, `source_location="1-618"`,
file measured at 618 lines).

| arm | mutation | result |
|---|---|---|
| C clean | none | `✓` rc=0 |
| A | every `source_location` -> `L999999` | **`✓` rc=0 — silent** |
| D (the REAL bug) | +11 on every numeric anchor; node0 span becomes `12-629` on a 618-line file | **`✓` rc=0 — silent**, via `mise run kb-validate-chunks` itself |
| **B control** | node0 `_origin` -> `"ast"` | `✗` rc=1, named the node and the reason |

So the probe discriminates: the validator CAN fail a chunk, it just cannot see an
out-of-range line anchor. Ran both through the real task and through
`uv run kb-setup validate-chunks` (mise.toml:1258 shows they are the same path).

## Transcript corroboration (round 672f23a4)

- `grep -n -o OFFSET` -> jsonl lines **1104** and **1164** (finding cited 1103/1163 — 1 off).
- Those two lines' commands name **two distinct** chunks:
  `SP/chunk-dotfiles-secrets-rule.json` and `SP/chunk-dotfiles-secrets-evidence.json`.
- jsonl 1170-1180 contains `lines 12-592` x4 and `591 lines` x4 — the hand-written
  range check that caught the out-of-range span.
- 19 of the Bash commands in jsonl 1080-1185 name a secrets chunk json — consistent
  with "~6 near-duplicate scripts per chunk" (spot-check / patch / re-verify triples).

## Refutation attempts that FAILED

1. Token spelling — searched `splitlines|line_count|num_lines|n_lines|lineno|anchor`
   across all of `python/src/kb_setup/`. `resolve.line_count` (resolve.py:660) EXISTS
   and is used by `handoff.py:289` (`_check_line_ref`) for handoff prose citations —
   the capability is in the repo, just never wired to chunks. Only caller of
   `citations` is `handoff.py`; nothing passes a chunk JSON to it.
2. Wrong artifact — ran the real `mise run kb-validate-chunks`, not just the module.
3. In-flight fix — `git diff --stat -- python/src/kb_setup/chunks.py` empty, tree clean.
4. Test coverage — `tests/test_chunks.py` has 15 `_origin` mentions and **0**
   `source_location` mentions.

## One correction to the finding's wording
"checks source_location SHAPE (AST vs semantic pattern)" is wrong about the code:
`_node_issues` never reads `source_location` at all (all 5 grep hits in chunks.py are
comment/message text; contrast `sf = n.get("source_file")` which IS a key read). The
module checks `_origin` explicitly *precisely so that* graphify's shape fallback is
never consulted (chunks.py:74-102). This makes the gap WIDER than stated, not narrower.

## Contradiction check against the other findings
None contradicts. Finding 3's sub-circle ("11-line caveat ... shifted every
source_location anchor in a completed 42-node chunk ... calls 0163-0169") is the same
incident seen from the docs/secrets.md side and CORROBORATES it; finding 3 names one
chunk, the transcript shows the patch ran on two. Finding 13 (heredoc bulk edits) is
the parent class of the "~6 one-off scripts".

**VERDICT: NOT REFUTED.**
