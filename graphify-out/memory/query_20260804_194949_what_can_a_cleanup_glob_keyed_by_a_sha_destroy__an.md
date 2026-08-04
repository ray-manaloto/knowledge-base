---
type: "query"
date: "2026-08-04T19:49:49.388240+00:00"
question: "What can a cleanup glob keyed by a SHA destroy, and how should copy-then-delete be sequenced?"
contributor: "graphify"
outcome: "useful"
---

# Q: What can a cleanup glob keyed by a SHA destroy, and how should copy-then-delete be sequenced?

## Answer

A cleanup glob keyed by a SHA cannot tell "my superseded copy" from "the only
copy" -- and a findings-bearing report is exactly the artifact that must not be
lost to one.

Writing this round's kb-review receipt I had lane reports keyed by an earlier
SHA and needed copies keyed by the final one. I ran:

    rm -f .agent/kb/review/reports/review-7a32c8e*.md

intending to clear MY superseded copies. That glob also matched the
silent-failure lane's ORIGINAL report -- the only copy on disk, written by the
agent at receipt per agent-report-persistence.md. The `cat` that was supposed to
copy it forward then silently produced a 15-line stub, and the stub looked
plausible enough to pass a casual glance.

It was recoverable only because the agent had also returned the report as its
final message, so the full text was still in the session transcript. That is
luck, not a control: a subagent report is normally consumed and dropped.

WHAT TO DO INSTEAD:
* Copy forward BEFORE deleting anything, never in the same command.
* When a glob is keyed by an identifier that other writers also use (a SHA, a
  date, a lane name), enumerate what it matches and read the list before running
  it -- `ls` the glob first.
* Check the RESULT of a copy, not just the rc of the command that wrote it. The
  stub was 15 lines where the source was 329; a `wc -l` immediately after would
  have caught it, and is what did catch it.

The general shape, which is why this is worth a memory rather than a shrug: the
receipt machinery makes filenames a CONTRACT -- kb_setup.review reads them -- so
the same naming that lets a gate find a report also lets a careless glob find it.
A contract on a filename is a reason to be MORE careful with globs over that
directory, not less.

## Outcome

- Signal: useful