# Refutation attempt — finding 30 (extraction-readiness), plan->preflight CLAUDE identity window

CLAIM: the plan->preflight Claude identity window is unchecked; a run today under
live claude 2.1.241 vs plan-pinned 2.1.240 would spend the budget and stage all
26 chunks failed on provider-version-identity-mismatch +
provider-executable-identity-mismatch. #426's shape, fixed for graphify, open for Claude.

## Source reads so far (primary artifact = installed repo source at HEAD)

- `python/src/kb_setup/graphify_semantic_slice.py:561` `_CURRENT_CLAUDE_VERSION = "2.1.240"`
  — a HARDCODED constant, not a live measurement.
- `graphify_semantic_corpus.py:261-264` `_CURRENT_CLAUDE = graphify_semantic_slice.current_claude()`
  -> `_CLAUDE_VERSION` / `_CLAUDE_EXECUTABLE_SHA256` / `_CLAUDE_HELP_SHA256`;
  `:882-885` writes them into the plan's `CorpusExecutionConfig`.
- `graphify_semantic_slice.py:1013-1085` `preflight()` MEASURES the live binary
  (`sha256_file(executable)`, `--version` regex, `--help` digest) and raises only on
  routing overrides / missing flags / unparsable version. It never compares any of
  the three to the plan config or to `_CURRENT_CLAUDE_*`.
- `graphify_semantic_corpus_run.py:1029-1060` `_assert_graphify_runtime_unchanged_since_plan`
  compares ONLY graphify fields; docstring says it mirrors `_adapter_overlay`'s
  Claude check "for the Graphify half of the identity rather than the Claude half".
- `graphify_semantic_corpus_run.py:445-447` `_adapter_overlay`'s Claude check is
  `sha256_file(real_path) != runtime.executable_sha256` where `runtime =
  context.preflight_receipt` — live-vs-PREFLIGHT, NOT live-vs-PLAN. So it closes the
  preflight->provider window, not the plan->preflight one.
- Exhaustive grep for the plan-side names (`claude_executable_sha256|claude_help_sha256|
  claude_required_flags`, and `claude_version`) finds comparisons ONLY at
  `graphify_semantic_corpus.py:2344/2347/2348/2350` (`_provider_runtime_reasons`) and
  `:2624/2628` (metadata) — both post-hoc, inside per-chunk staging.
- `graphify_semantic_corpus_run.py:733` `runtime=context.preflight_receipt` — the
  provider receipt's runtime IS the live measurement, so a live 2.1.241 lands in
  `runtime.version` and mismatches `config.claude_version`.
- `graphify_semantic_corpus_run.py:1213-1223` `_dispose` -> `_stage_or_failure(...)`
  appends an outcome; no raise. Loop continues; only `_SpendCapError` stops it.

STATUS: mechanism reads as the finding describes. Now running the empirical arms.

## Empirical arms (all run at HEAD d85f2835, branch corpus-gate-bundle-rebased)

### Arm 1 — live binary vs plan pin, WITH control

```
$ claude --version            -> 2.1.241 (Claude Code)     rc=0
$ readlink -f "$(command -v claude)"
                              -> /Users/rmanaloto/.local/share/claude/versions/2.1.241
$ shasum -a 256 <that>        -> 1495eb7c42d3b4451f5f1cd38b6d498d22a4a38c802bc2be5c1cf1795e64820d

CONTROL ARM (same probe, known-good input — the version the plan pins, still on disk):
$ shasum -a 256 ~/.local/share/claude/versions/2.1.240
                              -> 8917e01c99ea0ce6ed887a1729a4cda693c758fe542747be71756987b145c772
```
`8917e01c…` is byte-identical to `graphify_semantic_slice.py:562-564`
`_CURRENT_CLAUDE_EXECUTABLE_SHA256`. So the digest probe DISCRIMINATES: it
reproduces the pinned constant on 2.1.240 and a different value on the live
2.1.241. This is not a spelling/bound artefact.

Plan side:
```
$ grep -o '"claude_version":"[^"]*"' graphify-out/graphify-semantic-corpus/execution-config.json
"claude_version":"2.1.240"
$ grep -o '"claude_executable_sha256":"[^"]*"' .../execution-config.json
"claude_executable_sha256":"8917e01c99ea0ce6ed887a1729a4cda693c758fe542747be71756987b145c772"
```

### Arm 2 — `verify` authorizes anyway, WITH control

```
$ uv run kb-setup graphify-semantic-corpus verify
{"execution_authorized":true,"reasons":[],"state":"complete","structural_complete":true}   rc=0
```
CONTROL (proving verify CAN say no — plan copied to scratchpad and its Claude
identity rewritten to the LIVE 2.1.241/1495eb7c… values):
```
$ uv run kb-setup graphify-semantic-corpus verify <scratchpad>/plan-live
{"execution_authorized":false,"reasons":["member-digest-mismatch:execution-config.json"],
 "state":"failed","structural_complete":false}                                            rc=2
$ uv run kb-setup graphify-semantic-corpus verify <scratchpad>/plan-orig   (unmutated copy)
{"execution_authorized":true,"reasons":[],"state":"complete","structural_complete":true}  rc=0
```
Both directions fire, so the verify probe discriminates. And the control is
worse than the finding says: making the plan DESCRIBE THE LIVE BINARY is what
makes `verify` refuse. The authority is the hand-maintained constant
(`_effective_config` builds `expected` from `_CLAUDE_VERSION`,
`graphify_semantic_corpus.py:882-885`, compared at `_config_reasons` :1984), never
the installed binary.

### Arm 3 — exhaustive grep for a plan->preflight Claude comparison, WITH control

```
$ grep -n "preflight_receipt\|preflight(" python/src/kb_setup/graphify_semantic_corpus_run.py
359,438,733,801,1030,1043,1049,1060,1090,1094,1136
```
The only field-vs-plan comparison is line 1049
`if preflight_receipt.graphify_version != config.graphify_version:` — the
GRAPHIFY half. CONTROL: that hit proves this grep shape CAN find a
"live-vs-plan" comparison when one exists; there is no analogous line for
`version` / `executable_sha256` / `help_sha256` / `required_flags`.
The three "Claude ... changed after preflight" raises
(`graphify_semantic_slice.py:1877`, `graphify_semantic_corpus_prototype.py:143`,
`graphify_semantic_corpus_run.py:447`) all compare LIVE against the SAME RUN's
preflight receipt, never against the plan.

### Arm 4 — what a run would actually produce

- `graphify_semantic_corpus_run.py:733` `runtime=context.preflight_receipt` — the
  provider receipt's runtime is the LIVE measurement, so `runtime.version` = 2.1.241.
- `graphify_semantic_corpus.py:2344-2350` -> `provider-executable-identity-mismatch`
  and `provider-version-identity-mismatch` both fire.
- `graphify_semantic_corpus.py:2623-2630` adds TWO MORE the finding does not name:
  `provider-adapter-executable-mismatch` and `provider-adapter-version-mismatch`
  (`metadata.claude_version.startswith("2.1.240")` is false for "2.1.241 (Claude Code)").
- `graphify_semantic_corpus.py:2687` `status="failed" if reasons else "complete"`.
- `graphify_semantic_corpus_run.py:1213-1223` `_dispose` appends and returns; only
  `_SpendCapError` stops the loop.
- Ledger `"total":26`; `max_total_cost_usd = 63.0`. At the codebase's own measured
  $1.3249605/chunk the 26 chunks cost ~$34.4 — UNDER the cap, so the cap does not
  halt the run early. All 26 are attempted and all 26 stage `failed`.

## VERDICT: NOT REFUTED — confirmed, and if anything understated

The claim's only imprecision is "spend the whole budget": the run spends ~$34 of
the authorized $63 (26 x ~$1.32) rather than all of it, because nothing halts it
and nothing else costs. Every load-bearing element — unchecked plan->preflight
Claude window, `verify` authorizing today, both named reasons firing, all 26
chunks staged `failed`, graphify half fixed / Claude half open — reproduces.

## Contradiction check against the other 36 findings
None contradicts this one.
- #13 (`_ACCEPTED_CLAUDE_VERSION` 2.1.238 vs `_CURRENT_CLAUDE_VERSION` 2.1.240) is
  CORROBORATING: I read both constants at slice.py:475 and :561 and they are the
  hand-maintained literals whose drift is the mechanism here.
- #31 (cap $63 vs measured $1.3249605/chunk) is consistent with Arm 4's arithmetic
  and is what shows the spend cap does NOT halt the failing run early.
- #36 (pinned sources/graphify clone present) is corroborated: `verify` re-admitted
  the source and returned `structural_complete: true`.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under test; all reads are its own source and its own derived plan.
