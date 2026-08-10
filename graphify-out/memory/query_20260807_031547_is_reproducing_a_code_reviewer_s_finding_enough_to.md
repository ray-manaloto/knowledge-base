---
type: "query"
date: "2026-08-07T03:15:47.272063+00:00"
question: "Is reproducing a code reviewer's finding enough to verify it before fixing?"
contributor: "graphify"
outcome: "corrected"
correction: "REPRODUCING a reviewer's finding is NOT verifying it. A reproduction confirms what happens; it cannot confirm that what happens is WRONG — that needs the primary source. Worked case #219: a cold lane reported a `<<-` heredoc with an indented terminator being mis-parsed and the body corrupted; I reproduced it with a control arm that discriminated, and fixed it, and round 2 then found the fix had shipped the MIRROR defect. Going to bash settled it and corrected round 1 as well — `cat <<-'PY'` with a TAB-indented terminator terminates, with a SPACE-indented one does NOT (that line is body), and plain `<<'PY'` never does at any indent. The round-1 report's reproduction used SPACES, so the original code's output was FAITHFUL to bash and only the TAB case was ever a defect. The tell: a finding whose evidence is 'here is the output' rather than 'here is the output AND here is what the authority produces for the same input'. When a finding concerns a format, a protocol or a shell's semantics, the control arm is the REAL IMPLEMENTATION, not a second run of the same code. Two supporting facts: round 1 shipped 10 of 10 mutation arms green over a fix built on an unchecked premise, and the fix reshaped the exact text three arms mutate so the harness reported PROBE BROKEN — a state that must be distinguishable from SURVIVED or it scores as a false pass. Remedy adopted: every fix carries TWO arms, a REVERT (does its own test go red?) and a MIRROR (is the opposite over-correction caught?)."
---

# Q: Is reproducing a code reviewer's finding enough to verify it before fixing?

## Answer

Reproducing a reviewer's finding is NOT verifying it. A reproduction confirms
what happens; it cannot confirm that what happens is wrong. That needs the
primary source.

Worked case, #219, 2026-08-07. A cold lane reported P1: a `<<-` heredoc with an
indented terminator was mis-parsed, and the body "corrupted" by gluing in
unrelated shell commands. I reproduced it with a control arm — the control
behaved correctly, so the probe discriminated — and fixed it. Round 2 then
found the fix had shipped the MIRROR defect.

Going to bash settled it and corrected round 1 as well:

  cat <<-'PY' + TAB-indented   PY  -> terminates
  cat <<-'PY' + SPACE-indented PY  -> does NOT; that line is BODY
  cat  <<'PY' + any indent         -> does NOT

The round-1 report's reproduction used SPACES. So the original code's output was
FAITHFUL to bash, not corrupt. Only the TAB case was ever a defect. I had
reproduced the observation and never asked whether the observation was wrong.

The tell to watch for: a finding whose evidence is "here is the output" rather
than "here is the output AND here is what the authority produces for the same
input". When a finding concerns a format, a protocol or a shell's semantics,
the control arm is the REAL implementation, not a second run of the same code.

Two supporting facts from the same round:

- A clean mutation sweep did not help. Round 1 shipped 10 of 10 arms green over
  a fix built on an unchecked premise. Arms mutate an implementation; they
  cannot reach the question of whether the implementation implements the right
  rule.
- The fix reshaped the exact text three arms mutate, so the harness reported
  `PROBE BROKEN - pattern not found`. That state must be distinguishable from
  `SURVIVED` or it scores as a false pass. Rewrite the harness after a fix
  changes the lines it targets; do not re-point arms one at a time.

Remedy adopted: every fix now carries TWO arms - a REVERT (does its own test go
red?) and a MIRROR (is the opposite over-correction caught?). All three mirror
arms in this round correspond to defects a reviewer found, so the mirror arm is
not decoration.

## Outcome

- Signal: corrected
- Correction: REPRODUCING a reviewer's finding is NOT verifying it. A reproduction confirms what happens; it cannot confirm that what happens is WRONG — that needs the primary source. Going to bash showed the round-1 output was FAITHFUL and only the TAB case was ever a defect. When a finding concerns a format, a protocol or a shell's semantics, the control arm is the REAL IMPLEMENTATION, not a second run of the same code. Remedy adopted: every fix carries a REVERT arm and a MIRROR arm.