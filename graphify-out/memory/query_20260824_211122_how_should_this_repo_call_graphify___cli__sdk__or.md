---
type: "query"
date: "2026-08-24T21:11:22.915720+00:00"
question: "How should this repo call graphify — CLI, SDK, or internals?"
contributor: "graphify"
outcome: "corrected"
correction: "\"Use the CLI, not the library\" and \"do not re-implement the internals\" are\nDIFFERENT RULES, and I collapsed them into the first one for a whole round.\n\nRay said extraction should go through graphify rather than through a\nre-implementation. I wrote that down as \"CLI only\" and then reasoned from my own\nparaphrase: I ranked the subprocess module as the good pattern, flagged the\nin-process SDK module as the questionable one, put that ranking in a commit\nmessage, a docstring, an archive README and a published artifact, and asked Ray\na multiple-choice question whose options were built on it. He picked the option\nthat preserved the SDK module — and I recorded his reason as \"the ban is on\nre-implementing\" while continuing to describe the CLI as the destination.\n\nThe two readings only diverge on one file, which is why it survived so long. The\ntell was visible the entire time and I had already read it: the deleted layer\nimported `_estimate_file_tokens`, `_extraction_system`, `_pack_chunks_by_tokens`\nand `_read_files` — four LEADING UNDERSCORES — while the kept module called\n`graphify_sdk.public_api_fingerprint()`. Private versus a function whose name\nsays \"public API\". The distinguishing evidence was in a codex inventory I quoted\napprovingly, and I still did not re-derive the rule from it.\n\nThree things generalise:\n\n1. **A paraphrase of a directive becomes the directive.** Once \"do not\n   re-implement internals\" was written down as \"CLI only\", every later artifact\n   cited the paraphrase, and each citation made it more authoritative. Carry the\n   user's words verbatim into the durable artifact, not your compression of them.\n2. **When a user's answer surprises you, re-derive the rule instead of\n   recording the exception.** Ray choosing \"keep the SDK module\" was\n   inconsistent with \"CLI only\". I filed that as a carve-out. It was a\n   contradiction, and a contradiction is a signal the rule is wrong.\n3. **Public/private is a stronger line than in-process/subprocess.** The real\n   invariant is which surface the vendor promises to keep. `_name` is a promise\n   nobody made; a subprocess boundary is not automatically safer than a library\n   call to a documented function.\n\nThe cost was low only by luck: the deletion was correct on either reading, so\nnothing had to be undone. What had to be rewritten was every place the WRONG\nREASON had been recorded — four artifacts, which is this repo's recurring\nmeasurement about how far a wrong fact travels before someone re-derives it.\n"
---

# Q: How should this repo call graphify — CLI, SDK, or internals?

## Answer

# How should this repo call graphify — CLI, SDK, or internals?

Ray ruled the ranking on 2026-08-24, after a removal had already been framed the
wrong way round:

    1. BEST     call graphify's PUBLIC SDK directly, 1:1 with the CLI verb
    2. FALLBACK shell out to the CLI, for verbs with no public SDK method yet
    3. NEVER    import graphify's private internals

His words: "ideally graphify provides an sdk that is 1:1 with the cli so that
instead of running the graphify cli as a subprocess we would just call it
directly via the sdk ... it is these methods that we should be calling directly
instead of the cli - but not re-implement internal methods in graphify - and
hopefully one day graphify exposed every cli command as a public sdk method we
call directly."

## What this settles in the code

- `graphify_baseline.py` sits at rule 1 — it goes through `kb_setup.graphify_sdk`,
  whose `public_api_fingerprint()` exists to pin graphify's public surface. It
  was kept BECAUSE of that, not despite being in-process.
- `graphify_native_extract.py` sits at rule 2. It is a STOPGAP and should SHRINK
  as graphify promotes verbs to its public API. It had been documented as the
  destination, which was wrong.
- The removed semantic-corpus layer died on rule 3. From `graphify.llm` it
  imported `_estimate_file_tokens`, `_extraction_system`, `_pack_chunks_by_tokens`
  and `_read_files` — four private functions — and re-implemented planning,
  slicing and provider calls around them.

## Why the layer's drift follows directly from rule 3

Depending on private functions means depending on assumptions nobody promised to
keep. graphify #2900 added `.html` to `_SPLITTABLE_TEXT_SUFFIXES`; a 1,846,390-byte
excluded file went from ONE non-splittable unit to ~93 slices against a
20,000-char cap; and 24 tests went red on an assumption copied out of internals.
Rule 3 is not stylistic — it is what prevents that class of failure.

## The telemetry Ray wants back

The deleted `graphify_semantic_adapter.py` wrote an `adapter-metadata.json` per
chunk: full argv (including `--model claude-opus-5 --effort high`),
input/output/cache token counts, `total_cost_usd`, three duration fields,
executable and payload sha256s, auth method, returncode and stop_reason.

Two caveats before rebuilding: it instrumented the CLAUDE CLI (graphify's
provider backend), not graphify itself, so it is a template rather than a
drop-in; and `python/src/kb_setup/events.py` survives as the structured event
stream to hang a replacement on — `graphify_native_extract.py` already imports it.

Recover the reference implementation:

    git show d2acb5535553:python/src/kb_setup/graphify_semantic_adapter.py


## Outcome

- Signal: corrected
- Correction: "Use the CLI, not the library" and "do not re-implement the internals" are
DIFFERENT RULES, and I collapsed them into the first one for a whole round.

Ray said extraction should go through graphify rather than through a
re-implementation. I wrote that down as "CLI only" and then reasoned from my own
paraphrase: I ranked the subprocess module as the good pattern, flagged the
in-process SDK module as the questionable one, put that ranking in a commit
message, a docstring, an archive README and a published artifact, and asked Ray
a multiple-choice question whose options were built on it. He picked the option
that preserved the SDK module — and I recorded his reason as "the ban is on
re-implementing" while continuing to describe the CLI as the destination.

The two readings only diverge on one file, which is why it survived so long. The
tell was visible the entire time and I had already read it: the deleted layer
imported `_estimate_file_tokens`, `_extraction_system`, `_pack_chunks_by_tokens`
and `_read_files` — four LEADING UNDERSCORES — while the kept module called
`graphify_sdk.public_api_fingerprint()`. Private versus a function whose name
says "public API". The distinguishing evidence was in a codex inventory I quoted
approvingly, and I still did not re-derive the rule from it.

Three things generalise:

1. **A paraphrase of a directive becomes the directive.** Once "do not
   re-implement internals" was written down as "CLI only", every later artifact
   cited the paraphrase, and each citation made it more authoritative. Carry the
   user's words verbatim into the durable artifact, not your compression of them.
2. **When a user's answer surprises you, re-derive the rule instead of
   recording the exception.** Ray choosing "keep the SDK module" was
   inconsistent with "CLI only". I filed that as a carve-out. It was a
   contradiction, and a contradiction is a signal the rule is wrong.
3. **Public/private is a stronger line than in-process/subprocess.** The real
   invariant is which surface the vendor promises to keep. `_name` is a promise
   nobody made; a subprocess boundary is not automatically safer than a library
   call to a documented function.

The cost was low only by luck: the deletion was correct on either reading, so
nothing had to be undone. What had to be rewritten was every place the WRONG
REASON had been recorded — four artifacts, which is this repo's recurring
measurement about how far a wrong fact travels before someone re-derives it.
