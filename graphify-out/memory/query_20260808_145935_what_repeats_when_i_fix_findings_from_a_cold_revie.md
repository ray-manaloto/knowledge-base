---
type: "query"
date: "2026-08-08T14:59:35.560447+00:00"
question: "What repeats when I fix findings from a cold review of my own code?"
contributor: "graphify"
outcome: "useful"
---

# Q: What repeats when I fix findings from a cold review of my own code?

## Answer

Three review rounds over one branch produced 15 findings, and 6 of the last 8 were defects in the fixes written for the previous round. The single most repeated shape: Rule.unless in kb_setup.session_reflect is searched against the WHOLE command, which makes it the loosest thing in a rule, and it was written too wide three consecutive times on one rule (piped-rc). First rc=$? excused the very violation the rule names, because that $? belongs to tail. Then a bare PIPESTATUS word excused the wrong index and any prose mention. Then PIPESTATUS[0] without a dollar sigil still matched the literal text, so an echo of the words bought a full exemption while nothing expanded anything. Three instances of one shape means the shape is the defect: an exemption must name a form that occurs ONLY when the thing is really happening, and it needs its own must-STILL-fire arm, not just the rule's must-fire arm.

Second durable lesson: a config key can be read by the reporting path and by nothing that ACTS. currency tag_prefix reached only the sync-report comparison, never apply.py, so the check stopped reporting false drift on codex while an authorized auto-apply would still have aborted on no tag found. Wiring one call site is not wiring the feature, and the comment describing it is the least reliable evidence that it is done. That issue was then auto-closed by a merge keyword 14 minutes after being correctly reopened, so it read as done for a full round with the acting half still missing.

Third: quoting is not decoration in a shell-parsing regex. A leading quote was treated as skippable, but which quote decides what expands. Tilde expands only unquoted, and dollar forms expand unquoted or in double quotes but never in single. So cd with a double-quoted tilde path, and cd with a single-quoted HOME path, are RELATIVE targets naming directories literally called tilde and dollar-HOME, and both were excused by a rule whose whole subject is relative targets.

Fourth: a timing test can have no single-line mutant, and saying so beats shipping an arm predicted to survive. Restoring a quadratic spanning regex left the timing test green because scan checks the cheap Rule.also filter BEFORE the expensive pattern, and the adversarial input fails that filter. Measured 398 ms executing the pattern directly against those bytes versus 0.28 ms through scan. The short-circuit ORDER is the fix. The arm was written, ran, survived, and was removed rather than shipped, because a predicted survival is read as confirmation.

Fifth, mechanical but it cost two re-runs: a mutation spec anchors on source text, so every fix that edits a line invalidates some arm. Two arms broke in each of two successive commits. Run kb-arms with --dry-run after ANY edit, not only at the end. And an anchor whose leading whitespace does not match its line still applies as a substring at an offset, which happened to preserve indentation once and would silently write a syntax error the runner then scores as a DEATH.

## Outcome

- Signal: useful