---
type: "query"
date: "2026-08-10T05:23:15.965862+00:00"
question: "R5's sweep was scoped as a mechanical rename of 173 rc sites. What did auditing the sites first actually find?"
contributor: "graphify"
outcome: "corrected"
---

# Q: R5's sweep was scoped as a mechanical rename of 173 rc sites. What did auditing the sites first actually find?

## Answer

It is a RECONCILIATION, not a rename, and it falsified three figures I had already shipped in PR #267.

THE FINDING. mise-tasks-only.md documents the SAME failure two ways: line 72 says skill_lint's "glob matching nothing" exits 1; line 31 says kb-skill-score's "skill name matching nothing" is rc 2. check.py independently chose 2. distill returns a STRING (advisory, exits 0). One failure, three spellings, two of them documented in one file. So the claim that 175 sites "already agree" on the vocabulary was false -- Rc had named one of two competing conventions.

Ray ruled a FOURTH member rather than force the case into a code that misdescribes it: Rc.NOT_RUN. Neither 1 ("we looked and found something" -- we did not look) nor 2 ("you asked wrong" -- the request was fine).

ITS VALUE WAS NOT INVENTED. The repo had already chosen 127 for exactly this meaning, twice -- check.RC_COULD_NOT_RUN and gates._RC_COULD_NOT_RUN, both documented "distinct from any tool's own failure rc, so 'broken' never reads as 'failed'". Both now alias the member. Probed before adopting: no bare rc outside 0/1/2 is in use, and nothing branches on a specific non-zero code (every check is != 0), so no consumer changed.

TWO OTHER CORRECTIONS. "22 raise SystemExit(<str>)" is 19 -- three are SystemExit(main()), the canonical __main__ conversion and exactly the boundary the design argues FOR. "174 rc sites" is 173, and 8 of them are not exit codes at all: _dir_size, _node_count, _parse_size, _brew_freed_bytes, _as_int, line_count return QUANTITIES. Renaming those to Rc.OK would be a byte count asserting success.

THE PROBE LESSON. Getting the grep and the AST walk to agree required fixing my own analysis: bool subclasses int in Python, so isinstance(v.value, int) matched every `return True`/`False` and reported 228 against the grep's 173. Two routes disagreeing is what surfaced it; re-reading would not have.

SIDE EFFECT WORTH KEEPING. Adding a fourth member exposed that Ok's guard was a BLACKLIST (is Rc.BAD_REQUEST), which would have silently admitted Ok(rc=NOT_RUN). It is now closed (rc not in _RAN), so a fifth member is rejected by default. The fourth member did not cause that bug -- it revealed one already there.

Shipped as PRs #267 and #269. Conversion started (2 of ~30 modules) on feat/r5-sweep-conversion, unshipped.

## Outcome

- Signal: corrected