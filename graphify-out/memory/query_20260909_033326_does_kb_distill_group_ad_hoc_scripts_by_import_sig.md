---
type: "query"
date: "2026-09-09T03:33:26.646807+00:00"
question: "Does kb-distill group ad-hoc scripts by import signature?"
contributor: "graphify"
outcome: "corrected"
correction: "`kb-distill` groups by the repo SURFACE each script touches, NOT by import\nsignature — and it said the wrong thing about itself in five places.\n\n`distill.render()` printed \"Grouped by IMPORT SIGNATURE\" while `DEFAULT_POLICY`\nuses `surface_signature`, whose own docstring records that `import_signature`\nwas MEASURED AND REJECTED as the default (153 of 785 scripts landed in one\n`json` bucket). The literal survived the change that made it false, and four\nmore sites restated it: `mise.toml`, `session_reflect.py`'s module docstring,\n`.claude/skills/clear-prep/SKILL.md` and\n`.claude/skills/kb-session-reflect/SKILL.md`.\n\nWHY IT MATTERED BEYOND TIDINESS. Issue #717 argues from \"a frequency miner over\nimport signatures\", and the real limit is different in a way that HID EVIDENCE:\na surface-based grouping splits a habit SPANNING two surfaces across two rows by\ndesign. That is why `.agent/plans` (39 scripts) and `python/src/kb_setup` (28)\nread as two separate leads when the act is one shape — read/replace/write via a\npython heredoc, where the Edit tool is the native mechanism.\n\nFIXED BY CONSTRUCTION, not by retyping: `AXIS_BY_SIGNATURE` maps each signature\nFUNCTION OBJECT to its wording, `axis_of()` RAISES on an unregistered one rather\nthan defaulting, and `Report` carries the axis. A generated string cannot drift\nfrom its generator.\n\nTHE GENERAL LESSON: when a tool describes its own behaviour in a string, derive\nthat string from the behaviour. A literal survives the change that falsifies it,\nand every doc that quotes the tool then inherits the lie — here, four of them,\nincluding the issue that sent a round after the wrong fix.\n"
---

# Q: Does kb-distill group ad-hoc scripts by import signature?

## Answer

NO. `kb-distill` groups ad-hoc scripts by the repo SURFACE each one touches, not
by import signature.

`distill.DEFAULT_POLICY` sets `signature=surface_signature`, and
`surface_signature`'s own docstring records that `import_signature` was MEASURED
AND REJECTED as the default: over 40 real sessions it put 153 of 785 scripts in
one `json` bucket, which is a pile rather than a lead. Imports are only the
fallback for a script that touches no known surface.

WHY THE QUESTION HAD TO BE ASKED. `distill.render()` printed "Grouped by IMPORT
SIGNATURE" for months — a hardcoded literal describing the rejected policy, which
survived the change that falsified it. Four more sites restated it: `mise.toml`,
`session_reflect.py`'s module docstring, `.claude/skills/clear-prep/SKILL.md` and
`.claude/skills/kb-session-reflect/SKILL.md`. Issue #717 then argued from the
false description.

THE CONSEQUENCE THAT MATTERED. A surface-based grouping SPLITS a habit spanning
two surfaces across two rows by design. That is why `.agent/plans` (39 scripts)
and `python/src/kb_setup` (28) present as two separate leads when the act is one
shape: `read_text` -> `.replace()` -> `write_text` in a python heredoc, where the
harness's Edit tool is the native mechanism. Reading them as two leads is what a
correct-but-undocumented grouping axis costs.

FIXED in PR #718 (`a0b70c71`): `AXIS_BY_SIGNATURE` maps each signature FUNCTION
OBJECT to its wording, `axis_of()` RAISES on an unregistered one rather than
defaulting, and `Report` carries the axis, so the printed header is derived from
the policy that actually ran. Arms 3/3 died, 1/1 control held.


## Outcome

- Signal: corrected
- Correction: `kb-distill` groups by the repo SURFACE each script touches, NOT by import
signature — and it said the wrong thing about itself in five places.

`distill.render()` printed "Grouped by IMPORT SIGNATURE" while `DEFAULT_POLICY`
uses `surface_signature`, whose own docstring records that `import_signature`
was MEASURED AND REJECTED as the default (153 of 785 scripts landed in one
`json` bucket). The literal survived the change that made it false, and four
more sites restated it: `mise.toml`, `session_reflect.py`'s module docstring,
`.claude/skills/clear-prep/SKILL.md` and
`.claude/skills/kb-session-reflect/SKILL.md`.

WHY IT MATTERED BEYOND TIDINESS. Issue #717 argues from "a frequency miner over
import signatures", and the real limit is different in a way that HID EVIDENCE:
a surface-based grouping splits a habit SPANNING two surfaces across two rows by
design. That is why `.agent/plans` (39 scripts) and `python/src/kb_setup` (28)
read as two separate leads when the act is one shape — read/replace/write via a
python heredoc, where the Edit tool is the native mechanism.

FIXED BY CONSTRUCTION, not by retyping: `AXIS_BY_SIGNATURE` maps each signature
FUNCTION OBJECT to its wording, `axis_of()` RAISES on an unregistered one rather
than defaulting, and `Report` carries the axis. A generated string cannot drift
from its generator.

THE GENERAL LESSON: when a tool describes its own behaviour in a string, derive
that string from the behaviour. A literal survives the change that falsifies it,
and every doc that quotes the tool then inherits the lie — here, four of them,
including the issue that sent a round after the wrong fix.
