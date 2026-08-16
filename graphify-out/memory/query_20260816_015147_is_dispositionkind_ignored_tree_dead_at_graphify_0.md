---
type: "query"
date: "2026-08-16T01:51:47.698969+00:00"
question: "Is DispositionKind.IGNORED_TREE dead at graphify 0.9.44, now that #2759 stopped dropping tracked-but-gitignored files?"
contributor: "graphify"
outcome: "corrected"
correction: "I concluded the kind was unreachable and proposed retiring it. The reasoning was\na chain of true premises: a source snapshot is materialized from a commit, so\nevery file in it is tracked; #2759 stopped dropping tracked files matching\n.gitignore; therefore nothing in a snapshot can be ignored.\n\nEvery premise is true and the conclusion is still wrong as a statement about the\nKIND. Unreachability there is a property of how build_baseline happens to\nmaterialize source (clone plus detached checkout), not of graphify's classifier.\nRetiring the kind would have baked that assumption into a type, and any future\npath that is not a pure commit checkout -- a working-tree extraction, an\n--exclude, a vendored drop -- would silently lose the classification.\n\nThe correction: an \"unreachable by construction\" claim owes its own arm. Build\nthe reaching case and watch it be rejected. It took one probe and it refuted the\nplan. Do not reason your way to unreachability from premises, however sound.\n"
---

# Q: Is DispositionKind.IGNORED_TREE dead at graphify 0.9.44, now that #2759 stopped dropping tracked-but-gitignored files?

## Answer

No. It is still live at 0.9.44, and retiring it would have deleted a working
classification.

graphify #2759 changed one case only: a git-TRACKED file that also matches a
.gitignore pattern is no longer dropped, matching git's own behaviour of never
un-tracking such a file. An UNTRACKED path matching .gitignore still classifies
as ignored.

Measured at 0.9.44 across three repos, detection run on each:

  A  tracked + gitignored    -> no "ignored" key; file lands in files.document
  B  untracked + gitignored  -> "ignored": [".../secret/"]
  C  control, no .gitignore  -> neither; file is an ordinary document

C is what makes A and B evidence rather than opinion: without it, an empty
"ignored" in A proves nothing about the probe.


## Outcome

- Signal: corrected
- Correction: I concluded the kind was unreachable and proposed retiring it. The reasoning was
a chain of true premises: a source snapshot is materialized from a commit, so
every file in it is tracked; #2759 stopped dropping tracked files matching
.gitignore; therefore nothing in a snapshot can be ignored.

Every premise is true and the conclusion is still wrong as a statement about the
KIND. Unreachability there is a property of how build_baseline happens to
materialize source (clone plus detached checkout), not of graphify's classifier.
Retiring the kind would have baked that assumption into a type, and any future
path that is not a pure commit checkout -- a working-tree extraction, an
--exclude, a vendored drop -- would silently lose the classification.

The correction: an "unreachable by construction" claim owes its own arm. Build
the reaching case and watch it be rejected. It took one probe and it refuted the
plan. Do not reason your way to unreachability from premises, however sound.
