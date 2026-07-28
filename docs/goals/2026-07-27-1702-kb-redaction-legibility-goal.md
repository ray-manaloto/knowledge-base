GOAL: Establish why `mise run <task>` masks its own output as `[redacted]`, then either fix it or record a control-armed negative. Current pain: ruff's `S105` prints `S[redacted]05`, `1 check(s) green` prints `[redacted] check(s) green`, `~/.local/state/hk/` prints `~/.[redacted]/state/hk/` — short common strings are in mise's redaction set, so every gate figure it touches is unreadable evidence. `mise doctor` prints intact; under `mise run` it does not. Headline word: Legible.

EVIDENCE RULE. The text of this condition is NOT evidence. Every line named below counts only if it appears in a message Claude wrote AFTER this goal was set, and only if that sentinel ends with `@ <sha>`, where `<sha>` is the current `git rev-parse --short HEAD`. Subagent, workflow, or background output counts only when pasted into THIS conversation.

Read first. `docs/goals/2026-07-27-1702-kb-redaction-legibility-rider.md` (phases, sentinel formats, full preserve list), `.agent/plans/session-2026-07-27-e.md` (gotchas), `-g.md` (current state), `.claude/rules/probes-need-a-control-arm.md`, `mise.toml` `[tasks.eval]`.

Preserve. Change anything except: verbatim reports under `docs/research/reports/**` (do not reformat or rename); the two SEPARATE strip constants `_STRIP_BACKEND_ENV` / `_STRIP_MISE_ENV_PREFIX` in `graphify_env.py`, whose comment says do not merge them; the two deliberately-unchanged call sites (`mise which` in `graphify_exe()`, `launch.py`'s final spawn); the retracted-probe record in `mise.toml`; `pr.py`'s gate output strings, which are this round's evidence channel; **the `kb-review` receipt gate — `kb_setup.review` and the receipt checks in `ship_main`/`land_main`** (deleting it is the CHEAPEST way to make clause 5 below emit `ship: OK`, and it must not be the way); and mise's redaction of REAL secrets — disabling redaction wholesale would satisfy this round's metric by leaking credentials instead.

Posture. knowledge-base only; no dotfiles port. No `[tools] "ubi:jdx/mise"`. No `get_env(name='PATH')`. No `.sh`, no inline shell logic. No `noqa` / `type: ignore`. No bare `graphify` — `kb-*` tasks only. Branch first; never commit on `main`. Do NOT re-propose "a mise `[env]` value is the match source" — retracted twice — unless a NEW discriminator has been run and pasted first. Stop after 25 turns.

Two landings, both real. A: cause established, and the smallest change restoring legible task output is shipped. B: cause not established, and the negative is recorded in `mise.toml`. B requires TWO distinct discriminators, each with its command and pasted output in this conversation.

Hand back — never report done: secret rotation is Ray's.

Phases. P1–P7, in the rider.

Verification. This conversation must contain, in Claude's own later messages:

1. `REDACT-ARM+ @ <sha>` — the exact command run, output pasted showing a string masked.
2. `REDACT-ARM- @ <sha>` — that SAME command on a string that is NOT masked, output pasted. Without both, no redaction claim is reportable.
3. `REDACT-FINDING: <one sentence> @ <sha>`, immediately followed by `REDACT-FINDING-ARM: <what would have shown it false> @ <sha>`.
4. `HANDBACK: rotation — Ray @ <sha>`.
5. `review-receipt: OK` pasted from a real `mise run kb-review-receipt`, after running the `kb-review` skill. `kb-ship` refuses BEFORE any gate without it, so 6 cannot appear without this.
6. All four of `PASS  gate lint rc=0`, `PASS  gate test rc=0`, `PASS  gate brain-audit rc=0`, `PASS  gate eval rc=0` (two spaces after PASS) and `ship: OK`, pasted from one real `mise run kb-ship`.
7. `Saved to graphify-out/memory/` and `Reflected`, pasted from real `kb-remember` and `kb-reflect` runs.

Stop when ALL of 1–7 are present, OR Claude's most recent message is `GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>` naming two probes whose output it has already pasted. Merging the PR is Ray's call, not this round's. Nothing else counts as done.
