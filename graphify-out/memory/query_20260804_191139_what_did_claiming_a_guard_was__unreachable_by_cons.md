---
type: "query"
date: "2026-08-04T19:11:39.945787+00:00"
question: "What did claiming a guard was 'unreachable by construction' cost, and how should unreachability be established?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did claiming a guard was 'unreachable by construction' cost, and how should unreachability be established?

## Answer

"Unreachable by construction" is a CLAIM, and it needs an arm like any other.

Building #154 I kept a guard (`_LINE_REF_RE` inside `_typo_candidate`) and wrote,
in a code comment and in a committed mutation report, that it was unreachable.
The argument: for the pattern to match, a token ends in `:<digits>`, so its
extension contains a `:`; every entry in `_KNOWN_EXT` is short and alphanumeric;
therefore no such extension is ever within one edit of a known one.

Every premise is TRUE. The conclusion is FALSE. The chain never asked whether a
known extension ends in a DIGIT. `mp3` does. So `foo.mp:3` has extension `mp:3`,
delete the colon and you have `mp3` -- one edit. `_ext_repairs('mp:3')` returns
`('mp3',)`. Without the guard that token proposes `foo.mp3`.

The mutation arm for it had reported SURVIVED for two rounds and I had labelled
it "EXPECTED NO-OP by construction" in the harness itself, so the run kept
CONFIRMING my prediction. It did not survive because the code was undefended: it
survived because the TEST's fixtures (`cli.py:287`, `cli.pyx:287`) are far from
every known spelling either way, so removing the guard changes nothing for them.
A fixture unable to exhibit the harm -- which I had written into a different
test's docstring an hour earlier in the same session.

WHAT TO DO INSTEAD: to say "unreachable", CONSTRUCT the reaching case and watch
it be rejected. If you can construct it, it is reachable and you have just found
your fixture. If you genuinely cannot construct it after trying, that is when
the claim is earned. Deriving unreachability from a chain of true premises is
how a live guard gets reported dead -- and worse, how a confident label in the
harness turns every subsequent run into agreement rather than evidence.

Corollary: an arm you have PREDICTED will survive is the most dangerous kind,
because the prediction and the result confirm each other. Treat a predicted
survival as owing more evidence than an unexpected one, not less.

## Outcome

- Signal: useful