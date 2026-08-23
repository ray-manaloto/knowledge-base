# Refutation attempt — lane bot-reviews, finding 19 (check_first false-DENY)

CLAIM: `check_first.py` false-DENIES `ruff <global-option> help check` because
`_segment_is_a_gate` only tests `arguments[:1]` against `_INTROSPECTION_SUBCOMMANDS`;
live and un-dispositioned.

VERDICT: refuted = FALSE (could not refute). Two imprecisions, below.

## Probe (library level), HEAD d7e344f8
uv run python -c "... from kb_setup import check_first as c; c.decide(<cmd>)"
  DENY  'ruff --config x.toml help check'
  DENY  'ruff --isolated help check'
  DENY  'ruff --no-cache help check'
  ALLOW 'ruff help check'          <- CONTROL: probe CAN return None
  DENY  'ruff check .'             <- CONTROL: probe CAN deny a true gate
  ALLOW 'ty explain check', 'ruff --help check', 'ty --version', 'ruff rule E501'
Mechanism at python/src/kb_setup/check_first.py:243.

## END-TO-END arm — the LIVE PreToolUse hook, this session
  $ ruff help check            -> rc=0, printed ruff's help          (CONTROL: allowed)
  $ ruff --isolated help check -> hook DENY, "Do not hand-chain the gates..."
(`mise exec -- ruff ...` is NOT a valid arm: `mise` is not in _TRANSPARENT_PREFIXES,
so the guard reads `mise` as the command word and allows the line.)

## The denied command is REAL, not synthetic
  mise exec -- ruff --isolated help check                     -> rc=0
  mise exec -- ruff --config 'lint.line-length = 100' help check -> rc=0
  mise exec -- ruff --no-cache help check                     -> rc=2
     "error: unexpected argument '--no-cache' found" -> IMPRECISION 1: one of the
     three examples in the finding is not a valid ruff command at all.
`--config` and `--isolated` are listed under "Global options" in `ruff help`.

## Bot review exists, verbatim
gh api repos/ray-manaloto/knowledge-base/pulls/337/reviews/4957036793 --jq .body
  "**Global options before introspection subcommands cause false denials** —
   `python/src/kb_setup/check_first.py:218` · _Escalate · medium_"

## Logic unchanged since
git log -L 240,247:python/src/kb_setup/check_first.py --oneline
  -> ONE commit: e8f7f4ea "feat kb check guard (#337)". Never edited since.

## Disposition
- Issues: 209 enumerated; 0 mention check_first/false-deny.
  CONTROL: same file greps "guard|deny" -> #342,#319,#253,#239,#238,#210,#203,#120,#55
  and "kb-check" -> #290. Probe discriminates.
- IMPRECISION 2: a COMMITTED tracked doc already states it —
  docs/session-review/runs/2026-08-18-1/bot-reviews.md:70 (+ repro and
  "Disposition check" at :71-99), commit 2b7bd6ca. So it is RECORDED-but-unactioned,
  not unrecorded. That is round finding 1's meta-circle, not a contradiction.
