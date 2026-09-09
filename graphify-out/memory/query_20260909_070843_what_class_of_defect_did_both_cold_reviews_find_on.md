---
type: "query"
date: "2026-09-09T07:08:43.215931+00:00"
question: "What class of defect did both cold reviews find on 2026-09-09?"
contributor: "graphify"
outcome: "useful"
---

# Q: What class of defect did both cold reviews find on 2026-09-09?

## Answer

Both defects were the SAME CLASS, found in two different modules on the same day,
each by RUNNING the surface rather than reading it:

- **#687, `recall.py`.** `unparsable` was rendered "present but unreadable". The
  number is `real_total` minus what `load_memory_docs` returned, and that
  subtraction cannot separate a read failure from a readable `.md` that simply is
  not a memory document — `load_memory_docs` `continue`s identically for both.
  The COUNT was right; the WORD claimed one cause when only the union was
  measured.
- **#681, `memory_serve.py`.** `str(args.get("question", ""))`. `dict.get`'s
  default substitutes only when the key is ABSENT, so an explicit JSON `null`
  became the literal string `"None"` and was searched for — 60 matches in the
  382-record store, in a response shaped identically to a real answer.

The class: **a value that is correct for the common case and silently wrong for
the one case the caller cannot distinguish from success.** Neither produced an
error, a warning, or an odd-looking output. Both had correct neighbours that made
them invisible — for the null question, an omitted key and an empty string each
refuse properly, and the three OPTIONAL flags one line below already guarded
`is not None`; the only required field was the one without the guard.

**Reading did not find either.** #687's was found by a cold lane that constructed
an input and ran it; #681's by a cold lane that sent adversarial arguments over a
real stdio handshake. Three reading passes of my own had walked over the first.

The operational form: when a function has a default, ask what the caller can send
that ISN'T the absent case. When a count is a subtraction, ask what else lands in
it. In both places the honest fix was to narrow the claim to what was actually
measured, not to compute more.


## Outcome

- Signal: useful