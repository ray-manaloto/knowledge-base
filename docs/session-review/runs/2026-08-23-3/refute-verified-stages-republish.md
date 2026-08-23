# Refutation attempt — "_verified_stages re-publishes" doc/mise claim

CLAIM UNDER TEST (lane: contradicted): docs/agents/graphify-semantic-corpus.md and
mise.toml:684 both state "_verified_stages re-publishes every chunk whose stage
directory already holds verified evidence", contradicting the code.

VERDICT: refuted = false (the finding STANDS, and is stronger at HEAD than as filed).

## HEAD

964fb112 (one commit AFTER c720f1c9, which introduced both sentences).

## Probe 1 — do the sentences exist at HEAD?

    grep -n 're-publishes every chunk' docs/agents/graphify-semantic-corpus.md
    438:  for free.** `_verified_stages` re-publishes every chunk whose stage directory
    grep -n 're-publishes already-staged' mise.toml
    684:# `_verified_stages` re-publishes already-staged chunks so their evidence is

MY OWN FIRST PROBE WAS BOUND AND RETURNED A FALSE ZERO: `grep '_verified_stages re-publishes'`
matched nothing because the doc spells it "`_verified_stages` re-publishes" WITH BACKTICKS.
Re-grepped without the backtick bound; control = the same pattern at HEAD, which hits.

Line numbers: the finding cites docs:435-437. At c720f1c9 (where the sentence was born)
it is line 436; at HEAD it is 438 — 964fb112 shifted it. Off-by-a-line-or-three, text identical.

## Probe 2 — control-armed AST scan for WRITES (uv run python, not bare python3)

    _resolve_existing_stage 876-922  write-calls=[]
    _stage_or_failure       925-959  write-calls=[]
    _verified_stages        962-1000 write-calls=[]
    _dispose               1208-1218 write-calls=[(1218,'_stage_or_failure')]

CONTROL ARM (proves the scanner can return the other answer):
    _stage_completed_chunk 709-811: [(784,'stage_chunk')]
    _persist               224-240: [(234,'write_text')]
So the scanner DOES find publishers; it finds none in `_verified_stages`.

## Probe 3 — the dispatch, read directly (graphify_semantic_corpus_run.py:1208-1218)

    if chunk.ordinal in staged:
        outcome = _resolve_existing_stage(...)
        if outcome is None: repaid.append(chunk.ordinal)
        else: outcomes.append(outcome)
        return
    outcomes.append(_stage_or_failure(raw, chunk, context))

`stage_chunk` is reachable ONLY through the final line, i.e. only for a chunk with NO
existing stage dir. A verified stage returns before it. Skip, not re-publish.

## Probe 4 — four other in-repo statements agree with the code, not the doc

- run.py:23-24 (module docstring): a verified chunk "is skipped rather than re-published"
- run.py:884 (_resolve_existing_stage docstring): "so this pass must not re-publish it"
- graphify_semantic_corpus.py:3511: repaid = "staged, paid for again and not re-published"
- graphify_semantic_corpus.py:3545 / :3591 and completeness_rc: "not re-published"
- tests/test_graphify_semantic_corpus_run.py:1287: "`repaid` chunks were staged by an
  earlier pass and not re-published"

## Probe 5 — the doc sentence contradicts its OWN consequent

"…`_verified_stages` re-publishes every chunk … **so a restart does not write duplicate
artifacts** for what is already staged." Re-publishing is what would duplicate; the
non-duplication follows from SKIPPING. mise.toml:684 carries the same shape.

## Cross-check against the rest of the set

Finding 16 (58 chunks / 10.6h / $140 / '~1.5x') was TRUE at c720f1c9 and has since been
FIXED by 964fb112 (doc:416-435, mise:688-690 now read 26 chunks / 4.8h / 63.0 / 3.3x).
That commit rewrote lines 435 and 436 — immediately above — and left 438's "re-publishes"
untouched. Nothing in the set contradicts finding 17.

## Only unresolved caveat

`mise run kb-query -- "does _verified_stages re-publish or skip already staged chunks"`
returned uv/pytest/ruff AST nodes and then `ERROR task failed` (budget truncation) — the
aggregate graph does not carry this module's labels. Not evidence either way; source read.
