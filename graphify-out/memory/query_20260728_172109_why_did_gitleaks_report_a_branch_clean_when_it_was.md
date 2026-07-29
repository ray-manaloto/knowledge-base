---
type: "query"
date: "2026-07-28T17:21:09.070902+00:00"
question: "Why did gitleaks report a branch clean when it was not?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did gitleaks report a branch clean when it was not?

## Answer

Two independent reasons, both measured on 8.30.1 during #67. (1) gitleaks git shells out to git log -p; when THAT fails it logs the error, reports '0 commits scanned ... no leaks found', and exits 0 — so mapping rc=0 to clean makes any machine-local git misconfiguration a permanently green, permanently blind gate. Match its ERR/FTL lines BEFORE consulting rc, and pass --no-color, because gitleaks colours the log level even through a pipe and a plain ' ERR ' match otherwise finds nothing. Do NOT instead compare its 'N commits scanned' to the range size: a legitimate deletion-only branch also reports 0. (2) git log -p emits no patch for a MERGE commit, so a token introduced by the merge resolution and present in neither parent is scanned by nothing and logs no error either. --diff-merges=first-parent closes it. Also: gitleaks' default --exit-code is 1, which is ALSO its fatal-error code, so move findings to 2.

## Outcome

- Signal: useful