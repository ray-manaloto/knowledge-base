---
type: "query"
date: "2026-09-09T17:18:29.831564+00:00"
question: "Why does a push to dotfiles from an agent shell fail at the pre-push hook?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why does a push to dotfiles from an agent shell fail at the pre-push hook?

## Answer

dotfiles' pre-push hook step `test` runs `mise --cd "$MISE_PROJECT_ROOT" run test-hook-isolated`; the variable is only set by `mise activate`, and is empty in an agent Bash tool, under `git -C`, and even under `mise exec` (measured 2026-09-09). Every push from a non-activated shell fails with "Directory specified with --cd does not exist", which reads as a test failure. Remedy that honours the hook: `MISE_PROJECT_ROOT=<dotfiles> git -C <dotfiles> push …` — the suite then runs (2923 passed, 68.8 s). Never `--no-verify`. Filed on dotfiles.


## Outcome

- Signal: useful