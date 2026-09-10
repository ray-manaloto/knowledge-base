# kb-codex-advisor — does the currency/manifest/skill layer already advance a graphify pin's DERIVED values?

**Codex banner, verbatim from this lane's own run** (`OpenAI Codex v0.153.4`,
session `01a08818-8617-78c0-8720-d5bda539c57b`, rc=0):

```
model: gpt-5.6-sol
sandbox: read-only
```

(`reasoning effort: xhigh`, `approval: never`, `provider: openai`.) The reasoning below
ran inside `codex exec` via `mise run kb-codex -- --model gpt-5.6-sol --effort xhigh
--sandbox read-only --timeout 1500`. Full lane log and verdict are in this session's
scratchpad; the evidence table was gathered by the calling agent and handed to codex in
the prompt, and codex read the repo itself to confirm/refute it.

Commit under review: `5cb4b74e` on `feat/728-kb-fork-rebase` (#728).

---

## VERDICT: ABSENT.

No layer in scope automates advancing `source_tree`, `catalog_sha256` or
`source_manifest_sha256`. It is not specified-but-unbuilt either — no ticket, rule or
skill names those three values at all.

## The risk that decides it

**Auto-rewriting `_ACCEPTED_AUTHORITY` would convert a trust root into a checksum.**
`docs/agents/graphify-deterministic-baseline.md:~96`, verbatim:

> Rehashing a coherent but different candidate therefore cannot reauthorize omitted
> source, changed trust roots, or fabricated runtime/build evidence.

That is the whole point of the record. So "make `currency apply` write these four the way
it writes `ref`/`commit`" is the obvious fix and it is the wrong one: it would make the
build stop failing closed without anyone having looked at what changed. The correct shape
is *derive + present + require explicit acceptance*, never *derive + write*.

## Per sub-question

| layer | answer | evidence |
|---|---|---|
| **currency engine** | **No.** Bindings CHECK; they never write these, and cannot name them. | `currency.toml:216-248` declares exactly four `[[tool.graphify.ref_binding]]` rows, all `field = ref`\|`commit`. `config.py:385-435` parses a row; `RefBinding.tracks` is a validated enum (`config.py:122`). `sync.py:1656 _binding_want` resolves only those. `apply.py:4-8` docstring bounds an auto-apply to "the `mise.toml` pin and … its source manifest (`ref` → the new tag, `commit` → that tag's SHA)". |
| **manifest tooling / audit** | **No**, and the gate's green is true and narrow. | `manifest.py:24-30` — `Manifest` models `url`/`ref`/`commit` only. `manifest.py:418 write_pin` rewrites exactly those two lines. `manifest_audit.py` tier 1 = registry `pinned_commit` vs manifest `commit`; tier 2 = clone content hashes + zero-node coverage. Its own docstring, out-of-scope item 2: *"**Pin-site / currency-table completeness** … is a DIFFERENT check owned by `kb_setup.currency` — this gate does not couple into it."* None of the four stale values is in its domain. |
| **skills** | **NOT FOUND.** | `git grep "source_tree\|dispositions\|graphify_baseline\|ref_binding" -- .claude/skills/` → 0. **Control arm:** `graphify` → 44 hits in `kb-curator/SKILL.md`, 4 in `tool-currency/SKILL.md`, so the zero discriminates. `tool-currency/SKILL.md:~90` promises only the pin + manifest `ref`/`commit` edit. |
| **tickets** | **NOT FOUND for these three.** | `#728`'s Steps name *"`ref_binding` rows (`graphify_baseline.py`, `sources/graphify.dispositions.json`)"* as the unit of work — and the ref_binding table has four rows, none for a tree or a digest. `#728`'s "Done when" does not include `kb-graphify-baseline build`. `#739` (V1b) owns recurring *detection*, not derivation. `#647` is the same class one layer over and states the principle explicitly — *"A fix that only rewrites `pinned_commit` and carries the old hashes forward is **silently wrong**, because a stale hash still looks like a hash"* — but is scoped to `graph.py`'s registries and is folded into `#730`, not `#728`. |
| **rules** | **NOT FOUND.** | `git grep "derived value\|derived values\|pin site\|pin sites" -- .claude/rules/ CLAUDE.md .claude/CLAUDE.md` → rc=1, zero. **Control arm:** `manifest` matches 10 rule files. The memory note `a-tool-bump-must-advance-its-manifest` (Ray, 2026-08-08) is about the MANIFEST advancing and is not repo policy. |

## Why exactly two values advanced and four did not

The two that moved are precisely the two with `ref_binding` rows. The four that did not are
precisely the ones with none. Codex confirmed the correlation and added the correction that
matters: **`ref_binding` is a read-only equality CHECK, not a writer** — so even a fifth row
would not have advanced anything; it would only have gone red afterwards.

`ref_binding` is also the wrong *shape* for these values. `tracks = "manifest"` resolves the
wanted value out of `sources/graphify.manifest`, which carries `ref` and `commit` and nothing
else — no tree, no digest. A tree is derivable from the commit; the two digests are not
derivable from any pin file at all.

## Recommendation

**Fix it inside #728, before the review receipt and the PR.** #728 is mid-flight, unshipped,
gates 8/8, no receipt — this is the cheapest moment it will ever have. Amend its Steps to name
all four values explicitly (not "ref_binding rows") and add `kb-graphify-baseline build` to its
"Done when", since that is the check that actually fails closed on them. Put the derivation in
`kb_setup.fork_rebase` (the task #728 already owes): compute the tree and the candidate digests,
present them, and require explicit acceptance — never a silent write. #739 then *invokes* that
primitive rather than reimplementing it.

## Corrections to the calling agent's own framing

1. **`source_manifest_sha256` does not hash a file in this repo.** It hashes the GENERATED
   source-snapshot manifest (`graphify_baseline.py:583 def source_manifest(root, *, commit, tree)`),
   whose output lives under gitignored `graphify-out/graphify-baseline/`. The prompt asserted
   both digests were "hashes of files IN THIS REPO"; that half is wrong, and it changes the fix —
   these are outputs of a build, so they cannot be re-derived by reading tracked files.
2. **The DOCS layer is not silent, only the skills and rules are.**
   `docs/agents/graphify-deterministic-baseline.md` describes the authority record in prose —
   *"anchors the release ref, commit, tree, catalog digest, and complete source-manifest digest"* —
   though a literal grep for the field names returns 0 there. My "E. skills and rules say nothing"
   was correctly scoped; do not widen it to "nothing documents this".

## What could not be verified

- **Codex had no GitHub API access** from its read-only sandbox, so its reading of #728/#739/#647
  rests on the bodies pasted into its prompt, which the calling agent read live via `gh issue view`
  this session. Issue state is therefore verified by the caller, not independently by the lane.
- **Codex could not reach the graph**: `mise run kb-query` failed inside its sandbox with a
  temp-directory `Operation not permitted`, and a direct `graphify query` was denied by this repo's
  hook. Codex worked from source. The calling agent DID run `mise run kb-query` successfully
  (rc=3 truncation guard, 359,146 nodes, 351 found) and it surfaced `currency/apply.py:151` and
  `currency/skill.py:373` — consistent with, and narrower than, what the file reads showed.
- **Adjacent, not investigated:** `docs/agents/graphify-deterministic-baseline.md` still cites
  "410/402 AST admission counts" while `_ACCEPTED_AUTHORITY`'s own comments record 452→471 detected
  / 444→463 extracted. Same class of drift, different artifact. Not part of this question.

## Arms run by the calling agent (so the negatives are worth something)

- `git rev-parse 157a957e…^{tree}` → `707bdb5074beb3743e1c77f38db31c23a04f9497` (the stale value);
  `git rev-parse 3c9b930f…^{tree}` → `8fae076d840491419ab39fc05f0860007c0dcffe`. The stale value is
  provably the previous pin's tree. Run in `/Users/rmanaloto/dev/github/ray-manaloto/graphify`.
- `git grep "source_tree" -- python/src/kb_setup/currency/ python/src/kb_setup/manifest.py` → rc=1, 0 lines.
  Control: `manifest` in the same paths → 10 files with hits.
- `git grep "source_tree\|dispositions\|graphify_baseline\|ref_binding" -- .claude/skills/ .claude/rules/ docs/roadmap/` → 0.
  Control: `graphify` → 44 / 4 hits in two of those skill files.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; issues #726 #728 #729–#733 #739 #647 #701 read via `gh`.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — the fork checkout, where both tree-SHA arms were run.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — upstream, named by `currency.toml`'s `[tool.graphify] github` and `[tool.graphify.fork] upstream`; not fetched this session.
