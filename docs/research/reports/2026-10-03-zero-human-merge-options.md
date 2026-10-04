# Zero-human merge for the live-receipt check: options and recommendation (#824 / #837)

Research subagent (Opus), received 2026-10-03. This copy is persisted by the caller, because the agent's own append was refused by the worktree guard. It is condensed: the facts, the file:line anchors and the citations are kept intact.

## Five facts that change the question

1. **The agent can already merge anything.**
   - Sessions run on the env `GITHUB_TOKEN`, a classic PAT with the `repo`, `workflow` and `admin:org` scopes; no value was printed.
   - `permissions.admin=true` on the repo, and the agent's org role is admin.
   - So an agent can DELETE `enforce_admins`, delete branch protection, create rulesets, or push to `graphify-live-evidence`, which is `protected:false`.
2. **A producer already exists, unmerged.**
   - `python/src/kb_setup/live_receipt_produce.py` is 720 lines, in commits 4b31be8d and 7114bfe1 on `codex/cli-final-main-20260927`, `codex/kb-project-sync-v0971` and other branches.
   - It signs with `ssh-keygen -Y sign` using a private key file (produce.py:4, :679-705).
   - It assembles receipts from host artifacts; it does not run the cases itself.
   - The evidence branch holds 9 receipts, all under `receipts/822/`.
3. **The verifier checks the signature, not the work.**
   - It binds the PR number and head (live_receipt.py:200-207) and the `uv.lock` and graphify-manifest hashes (:227-241).
   - Graph hashes, node counts and producer receipts are self-reported (:148-171, :259-266).
   - A key the agent's user can read therefore adds no assurance.
   - Running the cases means running the PR's code, so a hostile PR is never caught.
4. **Most triggers are false positives.**
   - 96 of the 108 mise tasks are `run = "uv run …"`, so they trip `\buv\b` (scope.py:46-49, :134-141).
   - `cli.py` is in SENSITIVE_EXACT (:29).
   - #837 trips the check only through comments, new `uv run` task lines and a 4-line dispatch.
5. **The cost multiplies per head.** With `strict: true` and a head-bound receipt, every rebase needs a new 8-case live run, and receipts expire after 72h (:30).

## Current state (GET only, rc 0)

- **Protection:** the required check is "Verify signed exact-head live evidence" (app_id 15368, GitHub Actions), with `strict=true`. `enforce_admins=true`, 0 required approvals, conversation resolution required, force-push and delete off.
- **Rulesets:** none (`rulesets []`, `rules/branches/main []`).
- **Repo:** public, org on the Free plan, `allow_auto_merge=false`, 0 environments.
- **Workflow:** `pull_request_target`; checks out the base commit only and runs the base copy of scope.py. An EXEMPT result exits 0.
- **`pr.py`:** accepts check results of pass, skipping and neutral (:63-66). `checks_state` is at :195-265. The merge is `gh pr merge --squash --delete-branch --match-head-commit`, with no `--admin` (:830-858).

## Proposals

### P1 — Producer as a separate trusted daemon that runs the cases itself

- **How it works:** a launchd daemon runs under a separate macOS user that holds a 0600 key. It:
  1. fetches the exact head;
  2. runs the 8 cases with its own claude/codex logins;
  3. signs the result, reusing the assembly code;
  4. pushes the receipt with its own GitHub App or deploy key.
- **Evidence branch:** a ruleset restricts it so only that App/key can write.
- **What it protects:** receipts cannot be forged, and branch protection is never toggled.
- **Requirements:** case execution must be sandboxed away from the key, the agent user must have no sudo, and P7 is needed.
- **Cons:** the most expensive option (8 LLM cases per head), and it is laptop infrastructure.
- **Effort:** high, about 2-4 sessions.
- **P1-weak:** the key is held by the agent's own user. It is cheap, but the signature is meaningless.

### P2 — Narrow automated toggle (off, merge, on)

- **What it does:** DELETE `enforce_admins`, merge with `--admin`, then POST it back inside a `finally`, and verify with a GET.
- **Needs:** Administration write.
- **What it protects:** nothing new.
- **Risk:** a crash between the off and the on leaves main unprotected, and `--admin` also skips conversation resolution and `strict`.
- **Status:** Ray rejected it.

### P3 — Repository ruleset with a GitHub App bypass actor (pull_request mode), used only by kb-land

- **Setup:** delete the classic protection rule, because the most restrictive rule applies when both exist.
- **Bypass mode:** never use exempt mode, which writes no audit entry. Never add GitHub Actions (15368) as a bypass actor.
- **What it protects:** there is no toggle window, and the bypass is audited.
- **Cost:** the check is bypassed, not satisfied. Whoever holds the App key can merge anything.
- **Docs gap:** whether a CLI or API merge bypasses the check automatically is not documented. Probe it on a throwaway repo first.
- **Effort:** medium, plus a one-time human setup.

### P4 — Fix the scope check's false positives, staying fail-closed

- **Change:** compare TOML-parsed `mise.toml` instead of matching a regex. Require evidence only for:
  - the python/uv/pkl/graphify tools;
  - `[env]`, `[settings]` and `[deps.*]`;
  - the extraction tasks.
- **Also:** an AST diff of `cli.py`, so a dispatch-only addition is exempt.
- **Fail-closed:** any other change, or any parse failure, stays REQUIRED.
- **Bootstrap:** this needs one last manual merge.
- **Effort:** low to medium.
- **P4b (treat "no producer" as skip/neutral):** REJECTED. A job skipped by `if:` reports Success, and kb-land accepts the skipping bucket, so this would be a silent pass.

### P5 — Run the live cases in CI, unsigned

- **Setup:** LLM tokens live in a main-only environment.
- **Problem:** PR code runs next to those tokens under `pull_request_target`, the "pwn request" pattern.
- **Codex login:** whether a ChatGPT-plan codex login works in CI is unverified, and an API key would be metered (do-not.md #4).
- **Effort:** medium to high.

### P6 — Merge queue or auto-merge

- **Auto-merge:** only waits for checks; it neither satisfies nor bypasses them.
- **Merge queue:** requires the `merge_group` event, which our workflow lacks, so it would deadlock. The queued commit would also no longer be the head the receipt is bound to.

### P7 — Least-privilege agent credential (a prerequisite)

- **Change:** use a repo-scoped fine-grained PAT with Contents, Pull requests and Issues write, plus at most Administration read. Ray keeps the admin credential.
- **What it closes:** the threat Ray actually stated.
- **Effort:** low, but only Ray can do it.

## Who can do what

| State | Agent merges a REQUIRED PR alone? | Merge anything? | Crash leaves main unprotected? |
|---|---|---|---|
| Today | not via kb-land; yes by hand | yes | n/a |
| P2 | yes | yes | yes |
| P3, key under the agent user | yes | yes | no |
| P3 + P7, key under a separate user | yes | only via kb-land | no |
| P1-weak | yes | yes | no |
| P1 + P7 | yes, after a real run | no | no |
| P4 | only for false-positive PRs | unchanged unless P7 | no |
| P5 + P7 | yes, after a CI run | no, but secrets are exposed to PR code | no |

## Recommendation

> **Caller's annotation, 2026-10-03 (PR #865 review). The original text below is unchanged.**
>
> **What this annotation adds:** P3's fallback is missing a step.
>
> - `kb-land` (`python/src/kb_setup/pr.py`) sets no token of its own; it inherits the caller's `gh` credentials. For the ruleset bypass to apply, the merge must authenticate as the bypass App, which means minting and passing an App installation token. If the merge runs under a P7 fine-grained PAT, the App bypass does not apply, and the unmet check still blocks.
> - Any P3 build must specify that token handoff.
>
> **Status:** this does not affect the current plan. Ray's final ruling replaced P3 with a guarded admin-bypass mode (#864), which uses the existing admin credential and puts P7 (dotfiles#1613) on hold.

1. Do P7 first. Only Ray can, and until then every other option is policy only.
2. Do P4 next. It clears #837-class PRs, after one last bootstrap merge.
3. For real extraction changes, build P1 properly: a separate OS user that runs the cases and holds the key and the evidence-branch credential, reusing the unmerged `live_receipt_produce.py`. Do not ship P1-weak.
4. If P1 costs too much, use P3 instead: pull_request mode, gated in Python, with the App key held by the separate user. Say plainly that the check is bypassed, not satisfied.
5. Reject P2 and P4b.
6. Revisit `strict: true` separately.

## Citations

- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
- https://docs.github.com/en/rest/repos/rules
- https://docs.github.com/en/rest/branches/branch-protection
- https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens
- https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
- https://cli.github.com/manual/gh_pr_merge

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — protection, rulesets, repo settings, #824, the evidence branch, the workflow and scope/verifier/pr.py source (all read-only)
