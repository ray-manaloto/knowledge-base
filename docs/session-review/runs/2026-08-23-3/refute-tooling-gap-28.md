# Refutation lane: tooling-gap finding 28 (corpus-plan cluster)

Session under review: `5ec8da38-160b-4594-9560-c07a86b46f27` (16:57:19Z -> 18:17:09Z).
I am a sidechain of that same session, so its transcript is the primary artifact.

## Established so far

- `python/src/kb_setup/graphify_semantic_corpus.py:3146-3182` `corpus_main` takes
  `plan|run|verify [PATH]`; with `len(args)==2` `output = Path(args[1])`, else the
  default `repo_root / "graphify-out/graphify-semantic-corpus"`.
- The `plan` branch is exactly: `admit_source()` into a TemporaryDirectory, then
  `plan_source(source_root, output, source=pin, max_output_tokens=planned_max_output_tokens(...))`.
- `plan_source` (`:1294-1358`) writes ONLY into `output` (stage tempdir in
  `output.parent`, then `replace(output)`), and raises if `output.exists()`.
- `mise.toml` `[tasks.kb-graphify-semantic-corpus]` run = `uv run kb-setup graphify-semantic-corpus`.

## Transcript facts (main-thread only, isSidechain filtered)

207 main-thread tool_use; 159 of them Bash.
Calls 94, 95, 96 wrote scratchpad python that calls
`c.admit_source(...)` + `c.plan_source(..., max_output_tokens=c.planned_max_output_tokens(repo_root, os.environ))`
by hand -- i.e. a byte-for-byte reimplementation of `corpus_main`'s plan branch.

## The decisive two-armed probe (both arms run, 2026-08-22)

TARGET ARM -- the CLI with a scratch PATH:

```
$ uv run kb-setup graphify-semantic-corpus plan $SP/cliplan
rc=0
{"members":[{"name":"source-inventory.json","sha256":"f626c002...","size":200469}, ...]}
```

Byte-identity against the REAL plan directory (shasum -a 256 of all 6 members):

| member | scratch plan | graphify-out/graphify-semantic-corpus |
|---|---|---|
| advisories.json | ff7323b1921752cf195f0869b17f348903ffd8a196248be3c5edcece4fcc93d9 | same |
| chunk-ledger.json | 37aaa4622f732f29e246dee5321e881ee5fb9aab0bf1bcaaadb0c32ed5004f0a | same |
| exclusions.json | 1a63e48336f7130a1f68c57340706fd5cea3cbacf12c363bb339a7cae3e5b67e | same |
| execution-config.json | 710dbbfb2d15ac05c9857bd6f0e14ed03a9b7a858e85936a9adbda568938d9da | same |
| manifest.json | b4b741b5f0bb992c16f42b57f1e855c751e2de1c331dde1f979c1b80c8fad719 | same |
| source-inventory.json | f626c002e91f3842066361919b7a5b58ec78303585aba81156f1c8532dee55c6 | same |

Real directory mtime after my run: `Aug 22 12:49` (my run was 13:26); `git status --short`
empty. So the PATH form is genuinely non-destructive.

Those same six digests are the byte-literals the session hand-recorded into
`python/src/kb_setup/graphify_semantic_corpus_authority.py:621-657`.

CONTROL ARM -- the same command WITHOUT the PATH:

```
$ uv run kb-setup graphify-semantic-corpus plan
rc=1
ValueError: semantic corpus plan already exists: .../graphify-out/graphify-semantic-corpus
  (graphify_semantic_corpus.py:1307)
```

Same command shape, opposite answer. The probe discriminates.

## The in-session justification the finding names DOES exist

Transcript `5ec8da38`:
- 17:49:01Z tool_result: `mise run kb-graphify-semantic-corpus -- plan` (no PATH) ->
  `ValueError: semantic corpus plan already exists`.
- 17:52:31Z / 17:56:06Z / 18:17:07Z assistant: "`plan_source` REFUSES to overwrite an
  existing plan (fail-closed), so the old directory was backed up and removed first".

That is exactly the justification the finding says is contradicted, and the TARGET ARM
above contradicts it: the PATH argument (`_MAX_ARGS = 2`, `graphify_semantic_corpus.py:116`,
consumed at `:3153-3157`) sidesteps the existing-directory refusal entirely.

## VERDICT: refuted = FALSE. The finding stands.

## Caveats found (do not change the verdict)

1. Count: I measure **9** Bash calls driving `kb_setup` internals from python before the
   18:07:03Z review dispatch (`#54,55,57,58,73,91,94,95,96` in Bash-call order), and **13**
   across the whole session (`+123,151,152,154` after dispatch). The finding's "10" is
   reachable only if the denied bare `python3 -c` at Bash-call #18 is counted. +-1 on a
   supporting figure.
2. The cluster figures are EXACT: cluster = `#91,94,95,96` = **4**; the
   `admit_source()+plan_source()` reimplementation appears at `#94,95,96` = **three times**.
3. Scope note: the CLI's PATH form replaces the plan PRODUCTION only. Deriving "the admitted
   inventory as SETS" from `source-inventory.json` still needs some post-processing, and
   re-recording the digests into `graphify_semantic_corpus_authority.py` has no `record` verb
   (finding 2). Those are complementary, not contradictory.

## Cross-check against the other live findings

- Finding 2 ("no `record` verb; CLI is plan|run|verify only") is CONFIRMED by the same
  source read (`corpus_main` accepts only `{"plan","run","verify"}`) and does NOT contradict
  this one. It covers the authority re-record; this one covers plan production.
- Findings 27/29/30 (piped rc, hand-rolled stash dance) are consistent: Bash call #81 is
  `git stash -q && uv run ty check ... | tail -3`, and #80 is
  `mise run kb-check ... | tail -12; echo "KB-CHECK rc=${pipestatus[1]}"`.
- No finding in the set contradicts finding 28.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) - the repo under review.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) - materialized at the pinned
  `v0.9.48`/`b2cd3626` by `admit_source` during the target arm.
