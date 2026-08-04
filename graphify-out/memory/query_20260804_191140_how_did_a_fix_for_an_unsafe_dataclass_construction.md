---
type: "query"
date: "2026-08-04T19:11:40.478911+00:00"
question: "How did a fix for an unsafe dataclass construction reproduce the exact defect it removed?"
contributor: "graphify"
outcome: "useful"
---

# Q: How did a fix for an unsafe dataclass construction reproduce the exact defect it removed?

## Answer

A fix can reproduce, VERBATIM, the defect it was written to remove -- and its own
docstring will say otherwise.

Round 1 of review on #154 flagged Feature Envy: `resolve_extension_typo` built
`Index(files=idx.files, dirs=idx.dirs)` at the call site, dropping the vendored
tier by OMISSION, so any field the dataclass gained later would vanish silently.

My fix moved it onto the type as `Index.authored_only()`, with a docstring
explaining precisely that hazard. The body was:

    return Index(files=self.files, dirs=self.dirs)

The same construction. The same reliance on defaults. The failure mode was
RELOCATED, not removed, while the docstring now asserted a property the code did
not have. A cold round-2 lane found it by adding a fourth field to `Index` and
comparing against `dataclasses.replace`.

The general shape: when a finding is "this construction is unsafe", moving the
construction somewhere better does not make it safe. Ask what the SAFE
construction is (`dataclasses.replace(self, vendored=())` carries every field
forward and names the one being changed) and whether the fix uses it -- not
whether the fix is in a nicer place.

And the reason it survived my own review: I wrote the docstring describing the
hazard at the same moment I wrote the body reproducing it, so the prose agreed
with my intent rather than with the code. Two lessons already in this corpus
converge here -- "prose agreeing with itself is not verification" and "a fix can
be the defect" -- and they compound: the docstring is what stopped me re-reading
the one line beneath it.

## Outcome

- Signal: useful