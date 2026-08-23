# Refutation attempt — `_result_envelope` dead code (lane: bot-reviews)

Claim: repowise-bot flagged `_result_envelope` in graphify_semantic_adapter.py as dead
code on TWO separate PRs (#336 then #338); genuinely unused (only its own 3-line
definition); removed neither time.

## Probe 1 — is it unused? (word-bounded, repo-wide, no maxdepth)
```
grep -rnw '_result_envelope' --exclude-dir=.git --exclude-dir=.venv --exclude-dir=sources \
  --exclude-dir=graphify-out --exclude-dir=node_modules .
python/src/kb_setup/graphify_semantic_adapter.py:470:def _result_envelope(stdout: bytes) -> dict[str, object]:
docs/session-review/runs/2026-08-18-1/bot-reviews.md:365,374,378  (prose about it)
```
CONTROL ARM (same command shape, a private helper in the SAME file that IS used):
```
grep -rnw '_strict_json_integer\|_reject_non_json_constant' ... ->
python/src/kb_setup/graphify_semantic_adapter.py:35: def _reject_non_json_constant(...)
python/src/kb_setup/graphify_semantic_adapter.py:39: def _strict_json_integer(...)
python/src/kb_setup/graphify_semantic_adapter.py:374: parse_constant=_reject_non_json_constant,
python/src/kb_setup/graphify_semantic_adapter.py:375: parse_int=_strict_json_integer,
```
=> the probe DOES surface call sites when they exist. Unused stands.

Definition (sed -n '470,472p'), 3 lines, no docstring, no `__all__`, no getattr/globals()
dynamic access anywhere in the module.

## NOTE — the finding's OWN offered evidence is misstated
`grep -rn '_result_envelope' python/ tests/` returns **16 lines**, not "only its own
definition": `_result_envelope` is a SUBSTRING of `parse_result_envelope`. Unbounded
grep cannot produce the quoted result; only `-w` can. The conclusion survives, the
cited command does not.

## Probe 2 — was it flagged on TWO PRs, and by repowise?
repowise-bot posts ISSUE COMMENTS, not reviews (`/pulls/N/reviews` shows only
graphify-labs + coderabbitai). Correct route:
```
gh api repos/ray-manaloto/knowledge-base/issues/<N>/comments \
  --jq '.[]|select(.user.login=="repowise-bot[bot]")|.body' | grep -n '_result_envelope'
#336 -> 116:- 💀 `.../kb_setup/graphify_semantic_adapter.py` `_result_envelope` (confidence 0.65)
#337 -> (no match)          <-- CONTROL: the grep can return empty
#338 -> 87:- 💀 `.../kb_setup/graphify_semantic_adapter.py` `_result_envelope` (confidence 0.65)
#339 -> (no match)          <-- CONTROL
```
Exactly two PRs, exactly #336 and #338. Verified.

## Probe 3 — "removed neither time"
```
git show origin/main:python/src/kb_setup/graphify_semantic_adapter.py | grep -nw 'def _result_envelope'
  470:def _result_envelope(stdout: bytes) -> dict[str, object]:
git show HEAD:... -> same, line 470
```
Present on both. Introduced by 383288c0/cc6e226b (#308), refactored around by
ad8f408d/efea294b (#311) which added the public `parse_result_envelope`.

## Probe 4 — dynamic access (the usual escape hatch for "dead" verdicts)
No `getattr/setattr/monkeypatch.setattr` targeting it, no `import *`, no string
literal `"_result_envelope"` anywhere.
CONTROL: `grep -rn "monkeypatch.setattr" tests/ | wc -l` -> **609** — the pattern is
pervasive in this suite, so a zero here is a real zero, not a broken probe.

## Timing cross-check (bears on finding 25)
#336 merged 02:14:49Z, repowise commented 01:58:40Z -> the flag was on the PR
**16 minutes BEFORE merge** and still not acted on. #338 merged 04:33:31Z,
repowise 04:33:55Z (24s after). So for #336 "the bot was too late" is NOT the excuse.

## VERDICT: NOT REFUTED (refuted=false)
