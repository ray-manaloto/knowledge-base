# Refutation pass — finding [unpinned] #19

CLAIM: "Five direct 'uv run kb-setup graphify-semantic-corpus/slice' calls bypass existing
mise tasks kb-graphify-semantic-corpus and kb-graphify-semantic-slice; hook_guard has no
_REDIRECT entry for either, creating real coverage gap"

VERDICT: refuted=true (the mechanical halves hold; the load-bearing inference does not)

## What holds
- Tasks exist: mise.toml:665 `[tasks.kb-graphify-semantic-slice]` run="uv run kb-setup
  graphify-semantic-slice" timeout="30m"; mise.toml:679 `[tasks.kb-graphify-semantic-corpus]`
  run="uv run kb-setup graphify-semantic-corpus" timeout="16h".
- Count: 5 Bash tool_use call-sites in the reviewed session
  (~/.claude/projects/-Users-rmanaloto-.../6ae19ff6-2b88-4aea-8fa7-c0430395e2da.jsonl,
  firstTS 2026-08-21T06:08:40.927Z — the session this review covers):
  06:50:22.750Z slice preflight · 07:48:44.991Z slice verify · 08:28:24.736Z corpus plan+verify ·
  12:45:04.856Z slice verify · 13:24:41.906Z corpus plan+verify.
  A naive `grep -c` over the transcript returns SIX; the 6th (06:55:21.471Z) is a
  `cat >> .agent/notepad.md <<'EOF'` heredoc that merely MENTIONS the string. So 5 is right
  by luck-or-care, and the obvious probe over-counts by one.
- hook_guard has no entry: `grep -c "graphify-semantic|graphify_semantic|semantic-corpus|kb-setup"
  python/src/kb_setup/hook_guard.py` -> 0 (rc=1). CONTROL ARM: `grep -c "merge-graphs"` on the
  same file -> 1 (rc=0). Probe discriminates.
- Guard is silent at runtime, confirmed by running the decision function, control-armed:
    'uv run kb-setup graphify-semantic-corpus verify' -> None
    'uv run kb-setup graphify-semantic-slice verify'  -> None
    'graphify extract .' -> "Do not run `graphify extract` by hand. Use the mise task: mise run kb-build..."
    'uv run kb-setup session-state' -> None

## Why the inference is refuted
1. CATEGORY ERROR. `_REDIRECT` (hook_guard.py:68) is keyed on the **graphify subcommand**
   captured by `_GRAPHIFY_CMD` (hook_guard.py:37, consumed at :147). Its 16 keys are
   add/label/cluster/cluster-only/update/extract/merge-graphs/clone/query/save-result/reflect/
   add-watch/watch/install/uninstall/hook. It holds ZERO kb-setup command names — for ANY of
   the repo's kb-setup commands, not just these two. The remedy the finding names ("a _REDIRECT
   entry") is unimplementable in that dict; it would require a new pattern (the check_first
   shape), which is a different claim than the one made.
2. THE INVOCATION FORM IS SANCTIONED. `uv run kb-setup <cmd>` is this repo's documented way of
   invoking its own logic (zero-bash-logic.md: "invoked as `uv run kb-setup <cmd>`"), it is what
   three hk steps do (hk.pkl:286 no-lint-skip, :330 md-budget, :345 skill-lint), and
   mise-tasks-only.md names `uv run kb-setup session-state` as the CORRECT transport in one case.
   `decide('uv run kb-setup session-state') -> None` is therefore intended behaviour, not a hole.
3. THE ONLY FUNCTIONAL DELTA WAS INERT. The task adds nothing but mise's `timeout` key (and an
   echoed stderr banner). All 7 invocations across the 5 call-sites were provider-free
   preflight/verify/plan; NONE was the money/wall-clock action `run`, which is what the 16h/30m
   leashes exist to bound — and the harness's own Bash bound is tighter than either.
   CONTROL: `mise run kb-graphify-semantic-slice -- verify` -> rc=0, stderr banner
   "[kb-graphify-semantic-slice] $ uv run kb-setup graphify-semantic-slice verify", stdout
   {"state":"complete",...} — i.e. the task's body IS the "bypassing" command, byte for byte.
4. Cross-finding: #14 of this same round reports the graphify PreToolUse deny did NOT fire for
   Workflow-spawned subagents under bypass-permissions in this very session. If that holds, a
   new guard entry would not have stopped these calls either — the named remedy is doubly weak.

## Not contradicted by
No other live finding asserts these calls were harmful or that the tasks were unusable.
#13/#14 concern the same module (hook_guard) but the regex-vs-shlex and bypass-mode questions,
not this one.
