---
type: "query"
date: "2026-09-03T11:59:09.738059+00:00"
question: "Is refusing to parse a delimiter the safe direction for a guard tokeniser?"
contributor: "graphify"
outcome: "corrected"
correction: "REFUSING TO ACT IS NOT AUTOMATICALLY THE SAFE DIRECTION, and reasoning that it is\nproduced two P1 blind spots in a security guard.\n\nThe belief: when a tokeniser cannot confidently parse a heredoc delimiter,\nreturning None is safe, because an INVENTED delimiter never closes and silences\nthe guard for every command after it.\n\nThe half that is true: an invented delimiter really does blind the guard.\n\nThe half that was missed, and it is the whole lesson: refusing a delimiter that\nis REAL leaves its BODY exposed to the scanner. A body is attacker-shaped text.\nOne containing `<<NEVER` opens a heredoc nothing closes — blinding the guard by\nthe other route — and one containing `codex exec -` produces a false denial. Both\nfailure directions were reachable from the \"safe\" choice.\n\nWHAT SETTLED IT was neither reading the code nor reasoning about the shell: it\nwas RUNNING bash.\n\n    cat <<$VAR / body / EOF / $VAR   ->  EOF printed as BODY; $VAR terminated it.\n                                        Bash performs NO expansion on a heredoc\n                                        delimiter word.\n    cat <<\\ + EOF / body / EOF      ->  joined; the delimiter is EOF.\n\nBoth refusals were refusing real heredocs. Both were removed.\n\nTHE GENERALISATION: \"this can only fail safely\" is a CLAIM about a system with\ntwo failure directions, and it is only ever true if both have been checked. In\nthis round the same reasoning error appeared three times — the refusals, and a\ndocstring calling a multiple-heredoc limit conservative when a `<<NEVER` in the\nsecond body blinded all three guards. Every instance was written by someone who\nhad just read `probes-need-a-control-arm.md`.\n\nTwo corollaries worth carrying:\n\n- An ARM DEFENDING A BUG looks exactly like an arm defending a fix. Two arms in\n  this round protected the wrong refusals and died convincingly; only running the\n  shell showed which side they were on.\n- When a claim is about an EXTERNAL system's semantics (a shell, a CLI, a\n  platform), the primary source is the system. Reading our own code about it, or\n  its help text, is a secondary artifact — the same lesson as\n  `a-cli-error-string-is-not-its-capability`, arriving from a different direction.\n"
---

# Q: Is refusing to parse a delimiter the safe direction for a guard tokeniser?

## Answer

REFUSING TO ACT IS NOT AUTOMATICALLY THE SAFE DIRECTION, and reasoning that it is
produced two P1 blind spots in a security guard.

The belief: when a tokeniser cannot confidently parse a heredoc delimiter,
returning None is safe, because an INVENTED delimiter never closes and silences
the guard for every command after it.

The half that is true: an invented delimiter really does blind the guard.

The half that was missed, and it is the whole lesson: refusing a delimiter that
is REAL leaves its BODY exposed to the scanner. A body is attacker-shaped text.
One containing `<<NEVER` opens a heredoc nothing closes — blinding the guard by
the other route — and one containing `codex exec -` produces a false denial. Both
failure directions were reachable from the "safe" choice.

WHAT SETTLED IT was neither reading the code nor reasoning about the shell: it
was RUNNING bash.

    cat <<$VAR / body / EOF / $VAR   ->  EOF printed as BODY; $VAR terminated it.
                                        Bash performs NO expansion on a heredoc
                                        delimiter word.
    cat <<\ + EOF / body / EOF      ->  joined; the delimiter is EOF.

Both refusals were refusing real heredocs. Both were removed.

THE GENERALISATION: "this can only fail safely" is a CLAIM about a system with
two failure directions, and it is only ever true if both have been checked. In
this round the same reasoning error appeared three times — the refusals, and a
docstring calling a multiple-heredoc limit conservative when a `<<NEVER` in the
second body blinded all three guards. Every instance was written by someone who
had just read `probes-need-a-control-arm.md`.

Two corollaries worth carrying:

- An ARM DEFENDING A BUG looks exactly like an arm defending a fix. Two arms in
  this round protected the wrong refusals and died convincingly; only running the
  shell showed which side they were on.
- When a claim is about an EXTERNAL system's semantics (a shell, a CLI, a
  platform), the primary source is the system. Reading our own code about it, or
  its help text, is a secondary artifact — the same lesson as
  `a-cli-error-string-is-not-its-capability`, arriving from a different direction.


## Outcome

- Signal: corrected
- Correction: REFUSING TO ACT IS NOT AUTOMATICALLY THE SAFE DIRECTION, and reasoning that it is
produced two P1 blind spots in a security guard.

The belief: when a tokeniser cannot confidently parse a heredoc delimiter,
returning None is safe, because an INVENTED delimiter never closes and silences
the guard for every command after it.

The half that is true: an invented delimiter really does blind the guard.

The half that was missed, and it is the whole lesson: refusing a delimiter that
is REAL leaves its BODY exposed to the scanner. A body is attacker-shaped text.
One containing `<<NEVER` opens a heredoc nothing closes — blinding the guard by
the other route — and one containing `codex exec -` produces a false denial. Both
failure directions were reachable from the "safe" choice.

WHAT SETTLED IT was neither reading the code nor reasoning about the shell: it
was RUNNING bash.

    cat <<$VAR / body / EOF / $VAR   ->  EOF printed as BODY; $VAR terminated it.
                                        Bash performs NO expansion on a heredoc
                                        delimiter word.
    cat <<\ + EOF / body / EOF      ->  joined; the delimiter is EOF.

Both refusals were refusing real heredocs. Both were removed.

THE GENERALISATION: "this can only fail safely" is a CLAIM about a system with
two failure directions, and it is only ever true if both have been checked. In
this round the same reasoning error appeared three times — the refusals, and a
docstring calling a multiple-heredoc limit conservative when a `<<NEVER` in the
second body blinded all three guards. Every instance was written by someone who
had just read `probes-need-a-control-arm.md`.

Two corollaries worth carrying:

- An ARM DEFENDING A BUG looks exactly like an arm defending a fix. Two arms in
  this round protected the wrong refusals and died convincingly; only running the
  shell showed which side they were on.
- When a claim is about an EXTERNAL system's semantics (a shell, a CLI, a
  platform), the primary source is the system. Reading our own code about it, or
  its help text, is a secondary artifact — the same lesson as
  `a-cli-error-string-is-not-its-capability`, arriving from a different direction.
