---
type: "query"
date: "2026-09-03T17:12:42.183925+00:00"
question: "What is /verify, why is it never in my skill list, and can it be restored?"
contributor: "graphify"
outcome: "corrected"
correction: "`/verify` IS A BUNDLED CLAUDE CODE SKILL THAT WAS DELIBERATELY MADE\nUSER-INVOCABLE-ONLY, AND A PROJECT SETTING CAN GIVE IT BACK.\n\nRay, 2026-09-03, verbatim: \"add to graphify memory and anywhere else as we keep\nhaving this issue as it is only user invocable ... so you stop asking me that you\ndont know what this command is\".\n\nTHE CAUSE, primary source: `sources/claude-code-docs/content/CHANGELOG.md:1067`\n- \"Claude no longer runs the `/verify` and `/code-review` skills on its own;\ninvoke them with `/verify` or `/code-review` when you want them\".\n\nSo it is not missing and it is not unknown. It is a shipped bundled skill whose\nmodel invocation was switched off upstream. That is why it never appears in the\nsession's available-skills list while `/code-review` (restored since) does.\n\nTHE FIX, primary source: `sources/claude-code-docs/content/en/docs/claude-code/\nskills.md`, section \"Override skill visibility from settings\". `skillOverrides`\ntakes four values and the table is explicit:\n\n    \"on\"                  -> listed to Claude: Name and description | in / menu: Yes\n    \"name-only\"           -> listed to Claude: Name only            | in / menu: Yes\n    \"user-invocable-only\" -> listed to Claude: Hidden               | in / menu: Yes\n    \"off\"                 -> listed to Claude: Hidden               | in / menu: Hidden\n\n`/verify`'s observed behaviour - absent from the model's skill list, typable by\nthe user - is exactly the `user-invocable-only` row. Setting\n\n    {\"skillOverrides\": {\"verify\": \"on\"}}\n\nshould restore it to the model's context. The doc says `skillOverrides` \"controls\nskill visibility from your settings INSTEAD OF the skill's own frontmatter\", so it\noutranks frontmatter, and the `/doctor` example at `skills.md:32` shows the\nmechanism applied to a BUNDLED skill, which is what `/verify` is.\n\nSCOPE THAT KEEPS US INSIDE `do-not.md` #11: the `/skills` menu writes\n`skillOverrides` to `.claude/settings.local.json` - PROJECT scope. So this needs\nno write to `~/.claude` and is allowed here.\n\nONE CAVEAT, UNVERIFIED: \"Plugin skills are not affected by `skillOverrides`.\"\n`/verify` is bundled, not a plugin, so it should be affected - but that is read\nfrom the doc, not armed. The arm is cheap and must be run before this is treated\nas settled: set the key, reload, and check whether `/verify` appears in the\nsession's available-skills list. A doc-derived capability claim is exactly what\n`a-cli-error-string-is-not-its-capability` says to test rather than trust.\n"
---

# Q: What is /verify, why is it never in my skill list, and can it be restored?

## Answer

`/verify` IS A BUNDLED CLAUDE CODE SKILL THAT WAS DELIBERATELY MADE
USER-INVOCABLE-ONLY, AND A PROJECT SETTING CAN GIVE IT BACK.

Ray, 2026-09-03, verbatim: "add to graphify memory and anywhere else as we keep
having this issue as it is only user invocable ... so you stop asking me that you
dont know what this command is".

THE CAUSE, primary source: `sources/claude-code-docs/content/CHANGELOG.md:1067`
- "Claude no longer runs the `/verify` and `/code-review` skills on its own;
invoke them with `/verify` or `/code-review` when you want them".

So it is not missing and it is not unknown. It is a shipped bundled skill whose
model invocation was switched off upstream. That is why it never appears in the
session's available-skills list while `/code-review` (restored since) does.

THE FIX, primary source: `sources/claude-code-docs/content/en/docs/claude-code/
skills.md`, section "Override skill visibility from settings". `skillOverrides`
takes four values and the table is explicit:

    "on"                  -> listed to Claude: Name and description | in / menu: Yes
    "name-only"           -> listed to Claude: Name only            | in / menu: Yes
    "user-invocable-only" -> listed to Claude: Hidden               | in / menu: Yes
    "off"                 -> listed to Claude: Hidden               | in / menu: Hidden

`/verify`'s observed behaviour - absent from the model's skill list, typable by
the user - is exactly the `user-invocable-only` row. Setting

    {"skillOverrides": {"verify": "on"}}

should restore it to the model's context. The doc says `skillOverrides` "controls
skill visibility from your settings INSTEAD OF the skill's own frontmatter", so it
outranks frontmatter, and the `/doctor` example at `skills.md:32` shows the
mechanism applied to a BUNDLED skill, which is what `/verify` is.

SCOPE THAT KEEPS US INSIDE `do-not.md` #11: the `/skills` menu writes
`skillOverrides` to `.claude/settings.local.json` - PROJECT scope. So this needs
no write to `~/.claude` and is allowed here.

ONE CAVEAT, UNVERIFIED: "Plugin skills are not affected by `skillOverrides`."
`/verify` is bundled, not a plugin, so it should be affected - but that is read
from the doc, not armed. The arm is cheap and must be run before this is treated
as settled: set the key, reload, and check whether `/verify` appears in the
session's available-skills list. A doc-derived capability claim is exactly what
`a-cli-error-string-is-not-its-capability` says to test rather than trust.


## Outcome

- Signal: corrected
- Correction: `/verify` IS A BUNDLED CLAUDE CODE SKILL THAT WAS DELIBERATELY MADE
USER-INVOCABLE-ONLY, AND A PROJECT SETTING CAN GIVE IT BACK.

Ray, 2026-09-03, verbatim: "add to graphify memory and anywhere else as we keep
having this issue as it is only user invocable ... so you stop asking me that you
dont know what this command is".

THE CAUSE, primary source: `sources/claude-code-docs/content/CHANGELOG.md:1067`
- "Claude no longer runs the `/verify` and `/code-review` skills on its own;
invoke them with `/verify` or `/code-review` when you want them".

So it is not missing and it is not unknown. It is a shipped bundled skill whose
model invocation was switched off upstream. That is why it never appears in the
session's available-skills list while `/code-review` (restored since) does.

THE FIX, primary source: `sources/claude-code-docs/content/en/docs/claude-code/
skills.md`, section "Override skill visibility from settings". `skillOverrides`
takes four values and the table is explicit:

    "on"                  -> listed to Claude: Name and description | in / menu: Yes
    "name-only"           -> listed to Claude: Name only            | in / menu: Yes
    "user-invocable-only" -> listed to Claude: Hidden               | in / menu: Yes
    "off"                 -> listed to Claude: Hidden               | in / menu: Hidden

`/verify`'s observed behaviour - absent from the model's skill list, typable by
the user - is exactly the `user-invocable-only` row. Setting

    {"skillOverrides": {"verify": "on"}}

should restore it to the model's context. The doc says `skillOverrides` "controls
skill visibility from your settings INSTEAD OF the skill's own frontmatter", so it
outranks frontmatter, and the `/doctor` example at `skills.md:32` shows the
mechanism applied to a BUNDLED skill, which is what `/verify` is.

SCOPE THAT KEEPS US INSIDE `do-not.md` #11: the `/skills` menu writes
`skillOverrides` to `.claude/settings.local.json` - PROJECT scope. So this needs
no write to `~/.claude` and is allowed here.

ONE CAVEAT, UNVERIFIED: "Plugin skills are not affected by `skillOverrides`."
`/verify` is bundled, not a plugin, so it should be affected - but that is read
from the doc, not armed. The arm is cheap and must be run before this is treated
as settled: set the key, reload, and check whether `/verify` appears in the
session's available-skills list. A doc-derived capability claim is exactly what
`a-cli-error-string-is-not-its-capability` says to test rather than trust.
