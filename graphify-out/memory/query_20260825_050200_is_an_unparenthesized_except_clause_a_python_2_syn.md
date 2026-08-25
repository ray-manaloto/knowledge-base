---
type: "query"
date: "2026-08-25T05:02:00.803879+00:00"
question: "Is an unparenthesized except clause a Python-2 syntax error in this repo?"
contributor: "graphify"
outcome: "corrected"
correction: "`except A, B:` without parentheses is VALID on Python 3.14 (PEP 758), and this\nrepo uses it 69 times on a pinned 3.14.7. It is not a Python-2 relic and not a\ndefect.\n\nThe general lesson is larger than the syntax: a NEW LANGUAGE FEATURE reads exactly\nlike an OLD ERROR to any reader whose model of the language predates it, and\nbyte-level probes will agree with the wrong reading because the bytes really are\nwhat they look like. The tell is not in the bytes — it is that the file compiles.\n\nSo when a \"syntax error\" coexists with a module that imports, do not trust either\nobservation alone: ask the AST what the construct actually is\n(`ast.parse` then read the node type). Here `ast.ExceptHandler.type` resolves to a\n`Tuple`, which settles it in one command.\n\nTwo independent readers hit this in a single session and one of them raised it as\na blocking finding, so the cost is already measured: assume a third will, and\nprefer `requires-python` plus a PEP number in the explanation over \"it compiles,\ntrust me\".\n"
---

# Q: Is an unparenthesized except clause a Python-2 syntax error in this repo?

## Answer

BELIEF THAT WAS WRONG: that an unparenthesized `except` clause —
`except OSError, json.JSONDecodeError:` — is a Python-2 syntax error and therefore
a defect in this repo's code.

It is PEP 758, new in Python 3.14, and it is this repo's house style: 69 such
clauses across `kb_setup`, on a pinned 3.14.7 with `requires-python = ">=3.14"`.

What makes this worth recording is that TWO independent readers hit it in ONE
session, from opposite directions:

* I hit it first on `artifacts.py:76`. Byte-level probes agreed with the wrong
  conclusion — length 41, ZERO parentheses, codepoints confirming it — while the
  module imported fine and the AST parsed. I did not report it, because two probes
  disagreeing means one is broken, and it was mine: my "this line alone will not
  compile" snippet had malformed indentation.
* A cold premise-verifier lane then hit it on `cli.py:912` and made it a BLOCKING
  objection, asserting the module was unimportable and that the spec's own
  verification command could not run. Refuted the same way: `kb_setup.cli` imports,
  its AST parses, and `mise run kb-check` on that file is rc=0 across ruff, format
  and ty.

A third reader will hit it, and the danger is not the wasted probe — it is that
someone "fixes" 69 valid clauses by adding parentheses, or files a defect against
code that is correct.


## Outcome

- Signal: corrected
- Correction: `except A, B:` without parentheses is VALID on Python 3.14 (PEP 758), and this
repo uses it 69 times on a pinned 3.14.7. It is not a Python-2 relic and not a
defect.

The general lesson is larger than the syntax: a NEW LANGUAGE FEATURE reads exactly
like an OLD ERROR to any reader whose model of the language predates it, and
byte-level probes will agree with the wrong reading because the bytes really are
what they look like. The tell is not in the bytes — it is that the file compiles.

So when a "syntax error" coexists with a module that imports, do not trust either
observation alone: ask the AST what the construct actually is
(`ast.parse` then read the node type). Here `ast.ExceptHandler.type` resolves to a
`Tuple`, which settles it in one command.

Two independent readers hit this in a single session and one of them raised it as
a blocking finding, so the cost is already measured: assume a third will, and
prefer `requires-python` plus a PEP number in the explanation over "it compiles,
trust me".
