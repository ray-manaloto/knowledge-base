---
type: "query"
date: "2026-09-03T20:48:09.421326+00:00"
question: "Is it enough to repair a documented invariant in the file under review?"
contributor: "graphify"
outcome: "corrected"
correction: "REPAIRING A DOCUMENTED INVARIANT ONE FILE AT A TIME IS A TREADMILL. Fix every\nsite that states it, in one commit, or the next cold review finds the neighbour\nyou did not touch.\n\nMeasured 2026-09-03 across three rounds on `.claude/rules/do-not.md`:\n\n  round 1 (f16e9bd2) fixed 13 audit defects  -> cold review found 10 more\n  round 2 (de342beb) fixed 6 citations       -> cold review found 12 more, 3 of them P1\n  round 3 (9792b9e8) fixed all sites at once -> clean\n\nEVERY P1 IN ROUND 2's REVIEW WAS THE SAME DEFECT: one invariant stated in\nseveral places, corrected only where the reviewer was looking.\n\n- the retained `graphify-out/` exceptions: `do-not.md` said TWO (correct);\n  `.gitignore` said ONLY memory/ in two places and `CLAUDE.md` in a third. An\n  agent following onboarding would have untracked five retained files.\n- the Anthropic-key exception: round 2 added an accurate paragraph to CLAUDE.md\n  while the PRECEDING SENTENCE still said the opposite. The contradiction was\n  patched next to, rather than resolved.\n- the MCP policy: `do-not.md` forbade what `research-doc-sources.md` permitted,\n  and agents load both every session.\n\nTHE COUNT THAT MAKES IT STRUCTURAL, measured rather than estimated: the\ngraphify-out invariant appears in FOUR statements across THREE files, and\n`hk.pkl` contains NO cross-file consistency gate - grep for consistency /\ncontradict / cross-file returns nothing. So nothing in the repo can notice two\nauthorities disagreeing; only a cold review can, and only after it ships.\n\nWHAT TO DO:\n\n1. Before repairing a documented invariant, GREP FOR EVERY STATEMENT OF IT\n   first, and fix them together. `.gitignore` and `CLAUDE.md` count; so does any\n   rule file that restates rather than links.\n2. Re-measure against the world afterwards - `git ls-files graphify-out` - not\n   against the list you were handed. Round 3 did this and found the list was\n   right; that is the arm, not a formality.\n3. The durable fix is structural and is DEFERRED by Ray until after the\n   codex/mise deep extraction: a generated registry, so contradiction is\n   impossible rather than merely detectable. A cross-file consistency gate comes\n   AFTER that registry, because with generated prose there is nothing left to\n   catch.\n\nTHE SAME SHAPE, ONE LAYER DOWN, FOUND BY /verify AND STILL OPEN (#689): the\nguard that enforces this prints \"Use the mise task: NOT ALLOWED\" - the template\npromises a task name and interpolates a refusal string. Corrected in the\ndocument this round; still wrong in the code that enforces it.\n"
---

# Q: Is it enough to repair a documented invariant in the file under review?

## Answer

REPAIRING A DOCUMENTED INVARIANT ONE FILE AT A TIME IS A TREADMILL. Fix every
site that states it, in one commit, or the next cold review finds the neighbour
you did not touch.

Measured 2026-09-03 across three rounds on `.claude/rules/do-not.md`:

  round 1 (f16e9bd2) fixed 13 audit defects  -> cold review found 10 more
  round 2 (de342beb) fixed 6 citations       -> cold review found 12 more, 3 of them P1
  round 3 (9792b9e8) fixed all sites at once -> clean

EVERY P1 IN ROUND 2's REVIEW WAS THE SAME DEFECT: one invariant stated in
several places, corrected only where the reviewer was looking.

- the retained `graphify-out/` exceptions: `do-not.md` said TWO (correct);
  `.gitignore` said ONLY memory/ in two places and `CLAUDE.md` in a third. An
  agent following onboarding would have untracked five retained files.
- the Anthropic-key exception: round 2 added an accurate paragraph to CLAUDE.md
  while the PRECEDING SENTENCE still said the opposite. The contradiction was
  patched next to, rather than resolved.
- the MCP policy: `do-not.md` forbade what `research-doc-sources.md` permitted,
  and agents load both every session.

THE COUNT THAT MAKES IT STRUCTURAL, measured rather than estimated: the
graphify-out invariant appears in FOUR statements across THREE files, and
`hk.pkl` contains NO cross-file consistency gate - grep for consistency /
contradict / cross-file returns nothing. So nothing in the repo can notice two
authorities disagreeing; only a cold review can, and only after it ships.

WHAT TO DO:

1. Before repairing a documented invariant, GREP FOR EVERY STATEMENT OF IT
   first, and fix them together. `.gitignore` and `CLAUDE.md` count; so does any
   rule file that restates rather than links.
2. Re-measure against the world afterwards - `git ls-files graphify-out` - not
   against the list you were handed. Round 3 did this and found the list was
   right; that is the arm, not a formality.
3. The durable fix is structural and is DEFERRED by Ray until after the
   codex/mise deep extraction: a generated registry, so contradiction is
   impossible rather than merely detectable. A cross-file consistency gate comes
   AFTER that registry, because with generated prose there is nothing left to
   catch.

THE SAME SHAPE, ONE LAYER DOWN, FOUND BY /verify AND STILL OPEN (#689): the
guard that enforces this prints "Use the mise task: NOT ALLOWED" - the template
promises a task name and interpolates a refusal string. Corrected in the
document this round; still wrong in the code that enforces it.


## Outcome

- Signal: corrected
- Correction: REPAIRING A DOCUMENTED INVARIANT ONE FILE AT A TIME IS A TREADMILL. Fix every
site that states it, in one commit, or the next cold review finds the neighbour
you did not touch.

Measured 2026-09-03 across three rounds on `.claude/rules/do-not.md`:

  round 1 (f16e9bd2) fixed 13 audit defects  -> cold review found 10 more
  round 2 (de342beb) fixed 6 citations       -> cold review found 12 more, 3 of them P1
  round 3 (9792b9e8) fixed all sites at once -> clean

EVERY P1 IN ROUND 2's REVIEW WAS THE SAME DEFECT: one invariant stated in
several places, corrected only where the reviewer was looking.

- the retained `graphify-out/` exceptions: `do-not.md` said TWO (correct);
  `.gitignore` said ONLY memory/ in two places and `CLAUDE.md` in a third. An
  agent following onboarding would have untracked five retained files.
- the Anthropic-key exception: round 2 added an accurate paragraph to CLAUDE.md
  while the PRECEDING SENTENCE still said the opposite. The contradiction was
  patched next to, rather than resolved.
- the MCP policy: `do-not.md` forbade what `research-doc-sources.md` permitted,
  and agents load both every session.

THE COUNT THAT MAKES IT STRUCTURAL, measured rather than estimated: the
graphify-out invariant appears in FOUR statements across THREE files, and
`hk.pkl` contains NO cross-file consistency gate - grep for consistency /
contradict / cross-file returns nothing. So nothing in the repo can notice two
authorities disagreeing; only a cold review can, and only after it ships.

WHAT TO DO:

1. Before repairing a documented invariant, GREP FOR EVERY STATEMENT OF IT
   first, and fix them together. `.gitignore` and `CLAUDE.md` count; so does any
   rule file that restates rather than links.
2. Re-measure against the world afterwards - `git ls-files graphify-out` - not
   against the list you were handed. Round 3 did this and found the list was
   right; that is the arm, not a formality.
3. The durable fix is structural and is DEFERRED by Ray until after the
   codex/mise deep extraction: a generated registry, so contradiction is
   impossible rather than merely detectable. A cross-file consistency gate comes
   AFTER that registry, because with generated prose there is nothing left to
   catch.

THE SAME SHAPE, ONE LAYER DOWN, FOUND BY /verify AND STILL OPEN (#689): the
guard that enforces this prints "Use the mise task: NOT ALLOWED" - the template
promises a task name and interpolates a refusal string. Corrected in the
document this round; still wrong in the code that enforces it.
