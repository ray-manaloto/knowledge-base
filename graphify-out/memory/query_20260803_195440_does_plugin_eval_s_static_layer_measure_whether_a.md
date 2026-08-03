---
type: "query"
date: "2026-08-03T19:54:40.358817+00:00"
question: "Does plugin-eval's static layer measure whether a skill is CORRECT for the repo it runs in?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does plugin-eval's static layer measure whether a skill is CORRECT for the repo it runs in?

## Answer

No — it measures structure, not truth. A verbatim /clear-prep copied from a sibling repo, naming commands (dotfiles-setup verify run, check-doc-refs) that do not exist here, scored 65.6/100. The KB-native rewrite that fixed all of it scored 66.1. Control arm on the mechanism: renaming one word, 'orchestration' -> 'executor', in a sentence about which file to update moved the composite 6.4 points, because _score_orchestration applies a flat -0.15 penalty for the literal string. The heaviest lever the metric offered was a regex keyword. Use kb-skill-score to compare a skill against its OWN previous score and to find structural gaps (missing See also, no tables, thin frontmatter); never as a correctness gate, and never chase triggering_accuracy on a skill with disable-model-invocation: true, where it scores a trigger that must not exist.

## Outcome

- Signal: useful