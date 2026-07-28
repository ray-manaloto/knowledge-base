GOAL: Establish why `mise run <task>` masks its own output as `[redacted]`, then either fix it or record a control-armed negative. Current pain: ruff's `S105` prints `S[redacted]05`, `1 check(s) green` prints `[redacted] check(s) green`, `https://` prints `[redacted]s://`, `~/.local/state/hk/` prints `~/.[redacted]/state/hk/` — short common strings are in mise's redaction set, so every gate figure it touches is unreadable evidence. Run directly, `mise doctor` prints intact; under `mise run` it does not. Headline word: Legible.

EVIDENCE RULE. The text of this condition is NOT evidence. Every line named below counts only if it appears in a message Claude wrote AFTER this goal was set, and only if that sentinel ends with `@ <sha>`, where `<sha>` is the current `git rev-parse --short HEAD`. Work done inside a subagent, workflow, or background task counts only when its output is pasted into THIS conversation.

Read first. `docs/goals/2026-07-27-1702-kb-redaction-legibility-rider.md` (phases, sentinel formats, full preserve list), `.agent/plans/session-2026-07-27-d.md`, `.claude/rules/probes-need-a-control-arm.md`, `mise.toml` `[tasks.cc-doctor]`.

Preserve. Change anything except: verbatim reports under `docs/research/reports/**` (excluded from hk builtins — keep it so; do not reformat, do not rename); the two SEPARATE strip constants `_STRIP_BACKEND_ENV` and `_STRIP_MISE_ENV_PREFIX` in `python/src/kb_setup/graphify_env.py`, whose comment says do not merge them; the two deliberately-unchanged call sites (`mise which` in `graphify_exe()`, the spawn at the end of `launch.py`); the retracted-probe record in `mise.toml`; `pr.py`'s gate output strings, which are this round's evidence channel; and mise's redaction of REAL secrets — disabling redaction wholesale would satisfy this round's metric by leaking credentials instead.

Posture. knowledge-base only; no dotfiles port. No `[tools] "ubi:jdx/mise"`. No `get_env(name='PATH')`. No `.sh`, no inline shell logic. No `noqa` / `type: ignore`. No bare `graphify` — `kb-*` tasks only. Branch first; never commit on `main`. Do NOT re-propose "a mise `[env]` value is the match source" — retracted twice — unless a NEW discriminator has been run and pasted first. Stop after 25 turns.

Two landings, both real. A: cause established, and the smallest change restoring legible task output is shipped. B: cause not established, and the negative is recorded in `mise.toml` with the discriminators that failed to find it. B requires at least TWO distinct discriminators, each with its command and its pasted output in this conversation.

Hand back — never report these done: secret rotation is Ray's, and the CodeRabbit "Review rate limited" policy call is Ray's.

Phases. P1–P7, in the rider.

Verification. This conversation must contain, in Claude's own later messages:

1. `REDACT-ARM+ @ <sha>` — naming the exact command run, with its output pasted showing a string masked.
2. `REDACT-ARM- @ <sha>` — that SAME command on a string that is NOT masked, output pasted. Without both, no redaction claim is reportable.
3. `REDACT-FINDING: <one sentence> @ <sha>`, immediately followed by `REDACT-FINDING-ARM: <what would have shown it false> @ <sha>`.
4. `HANDBACK: rotation — Ray @ <sha>` and `HANDBACK: coderabbit — Ray @ <sha>`.
5. All four of `PASS  gate lint rc=0`, `PASS  gate test rc=0`, `PASS  gate brain-audit rc=0`, `PASS  gate eval rc=0` (two spaces after PASS) and `ship: OK`, pasted from one real `mise run kb-ship`.
6. `Saved to graphify-out/memory/` and `Reflected`, pasted from real `kb-remember` and `kb-reflect` runs.

Stop when 1–6 are all present, OR Claude's most recent message is `GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>` naming two probes whose output it has already pasted. Merging the PR is Ray's call, not this round's. Nothing else counts as done.
