---
type: "query"
date: "2026-08-03T18:56:03.750208+00:00"
question: "Where does /clear-prep live, and why did a four-location search conclude it was gone?"
contributor: "graphify"
outcome: "useful"
---

# Q: Where does /clear-prep live, and why did a four-location search conclude it was gone?

## Answer

It is a DOTFILES project skill: ~/dev/github/ray-manaloto/dotfiles/.claude/skills/clear-prep/SKILL.md, added in dotfiles PR #123, never deleted, tracked in HEAD. Claude Code loads project skills from the CURRENT project, so it simply does not exist in a knowledge-base session — correct scoping, not a loss. Copied into this repo 2026-08-03 (4d04ccb) verbatim from dotfiles@d85afaad with a banner naming every dotfiles-specific line, because four tracked docs here cite it including docs/direction/2026-08-02-ray-directives.md ('Captured at /clear-prep'). TWO BOUNDS made me report it GONE: (1) I searched this project + ~/.claude/skills + ~/.claude/commands + all ~40 plugin marketplaces and NOT the sibling repo — probes-need-a-control-arm rule 3, and the control proves the probe was fine since the same grep aimed one directory over finds it instantly; (2) its frontmatter carries disable-model-invocation: true, which hides it from every skill listing, so 'absent from listings' felt like corroboration when it was just the flag working. When a skill seems missing, search SIBLING PROJECTS before concluding absence — a project skill is invisible from every other project by design.

## Outcome

- Signal: useful