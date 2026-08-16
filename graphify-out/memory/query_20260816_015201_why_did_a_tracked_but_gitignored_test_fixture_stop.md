---
type: "query"
date: "2026-08-16T01:52:01.791109+00:00"
question: "Why did a tracked-but-gitignored test fixture stop being detected at graphify 0.9.44?"
contributor: "graphify"
outcome: "corrected"
correction: "The first reading was: \"0.9.44 silently drops tracked-and-gitignored files --\nworse than 0.9.43, which at least reported them as ignored.\" That would have been\na false and alarming claim about the release, and it was one edit from being\nwritten into a commit message.\n\nIt survived initial scrutiny because it was consistent with the evidence in hand:\nthe file was in neither the ignored bucket nor any detected bucket, and the\nrelease notes had just changed exactly this area. A wrong conclusion adjacent to\na real change reads as caused by it.\n\nWhat caught it was a SECOND probe of the same fact by a different route -- an\nearlier three-repo arm in which a tracked+ignored file WAS detected. Two probes\nof one fact disagreed, so one of them was broken, and the disagreement located\nthe real variable in two runs.\n\nThe correction: when a probe result surprises you AND a plausible culprit is\nalready on the table, that is when to cross-check, not when to skip it. The\nnearby change is the most attractive wrong explanation available.\n"
---

# Q: Why did a tracked-but-gitignored test fixture stop being detected at graphify 0.9.44?

## Answer

Because graphify 0.9.44 skips a file whose NAME begins "secret.", regardless of
gitignore. Nothing to do with #2759.

Isolated by holding the directory, the .gitignore content and the commit shape
fixed and changing only the filename:

  ignored/secret.txt  + ignored/secret.md   -> neither detected, "ignored" empty
  ignored/design.txt  + ignored/design.md   -> BOTH detected

Same repo shape, same pinned graphify, one variable. #2759 works exactly as
documented, and the real corpus proves it independently: the graphify baseline
went 410 -> 417 detected at the bump, and two of those seven are
docs/superpowers/*.md, which are tracked and gitignored.

The fixture had never exercised the filename before, because the pre-0.9.44
assertion looked at the ignored DIRECTORY rather than the file.


## Outcome

- Signal: corrected
- Correction: The first reading was: "0.9.44 silently drops tracked-and-gitignored files --
worse than 0.9.43, which at least reported them as ignored." That would have been
a false and alarming claim about the release, and it was one edit from being
written into a commit message.

It survived initial scrutiny because it was consistent with the evidence in hand:
the file was in neither the ignored bucket nor any detected bucket, and the
release notes had just changed exactly this area. A wrong conclusion adjacent to
a real change reads as caused by it.

What caught it was a SECOND probe of the same fact by a different route -- an
earlier three-repo arm in which a tracked+ignored file WAS detected. Two probes
of one fact disagreed, so one of them was broken, and the disagreement located
the real variable in two runs.

The correction: when a probe result surprises you AND a plausible culprit is
already on the table, that is when to cross-check, not when to skip it. The
nearby change is the most attractive wrong explanation available.
