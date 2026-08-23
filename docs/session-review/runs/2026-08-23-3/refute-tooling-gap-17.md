# Refutation lane: finding 17 (kb-session-reflect missed the gh api chains)

Claim: kb-session-reflect reported "nothing — every step went through its task"
BECAUSE its shape-matcher normalizes command TEXT and cannot see a repeating
STRUCTURE across calls whose URL/--jq/body differ.

## Primary artifact reads (in progress)

- `python/src/kb_setup/session_reflect.py:766-771` — the quoted string
  "nothing — every step went through its task" is the EMPTY placeholder of the
  section rendered from `report.owned`.
- `report.owned` is computed at `session_reflect.py:663` as
  `scan(OWNED, command, session)`. `OWNED` is a 4-row regex table at
  `session_reflect.py:212-268`: `mutation-harness`, `graph-counts`,
  `manifest-pin`, `gate-by-hand`. **No normalisation is applied to it at all.**
- `_normalise` (`session_reflect.py:518-529`) feeds a DIFFERENT section,
  `report.repeats` -> "Command shapes repeated inside ONE session"
  (`session_reflect.py:672-673`, rendered at :789-791).

=> The quoted output and the stated cause belong to two different mechanisms.

## The decisive probes

### 1. The quoted string comes from a section the normalizer does not feed
`session_reflect.py:766-771` renders `report.owned` with empty-placeholder
"nothing — every step went through its task". `report.owned` = `scan(OWNED, …)`
(`:663`), a 4-rule regex table (`:212-268`: mutation-harness, graph-counts,
manifest-pin, gate-by-hand) — **no `_normalise` call anywhere on that path**.
`_normalise` (`:518-529`) feeds only `report.repeats` (`:672-673`).

### 2. The normalizer DOES see structure across differing URL/--jq/body
CONTROL ARM — real `reflect()` on a 5-command synthetic transcript:
```
commands scanned: 5
REPEATS:
  x2 'gh api reposP --jq Q'            <- 2 reads, different URL AND different --jq
  x2 'gh api -X POST reposP -f body=Q' <- 2 POSTs, different comment id AND body
```
(`git status --short` correctly absent => the detector discriminates.)
`_normalise` maps quoted strings->Q, `/…`->P, digits->N, so URL/--jq/body are
exactly what it erases. The stated mechanism is the opposite of the code.

### 3. What actually happened in the round
Transcript `096161cc-2a22-4b34-ad40-168e202bd37f.jsonl`, the one the cited
tool_use `toolu_01LWUEVNuLvxSqi9UB4BYgn9` lives in (line 865 tool_use / 866
tool_result). Its output header: `1 session(s), 50 bash command(s) scanned`,
and the transcript has exactly 50 Bash tool_use blocks at/below line 866
(60 total) — so it scanned this session, whole.
- Bash commands containing `gh api`: **3** (lines 412, 425, 680), not 9.
- `gh api` textual invocations inside them: **8**.
- All 8 POST replies live inside ONE Bash command (line 680, a `reply()`
  shell function invoked 8x inline).
=> Each of the 3 is a distinct composite pipeline occurring ONCE, so count 1 <
`MIN_RUN = 2` (`:63`, `:673`). The reason is per-command uniqueness and the
8-in-1 bundling, NOT text-vs-structure normalisation.

### 4. The OWNED section's "nothing" was CORRECT by its own definition
Section title is "Hand-rolled work **a mise task already owns**". No mise task
reads PR bot comments — `grep '^\[tasks\.' mise.toml | grep -iE 'bot|comment'`
=> rc=1 (control: the same grep for `review` returns kb-skillopt-reviewed,
kb-review-receipt). #462 is OPEN precisely because that reader does not exist
(finding 15). A tool that reports work an existing task owns cannot report work
no task owns.

### 5. Control arm that the OWNED section CAN be non-empty
Same tool, same code, different transcript
(`48d40647-9738-4086-ab85-4eb80bd870bc.jsonl`, 229 commands):
"## Hand-rolled work a mise task already owns" printed **3 `mutation-harness`
rows**. So the empty result is a real negative, not a broken section.

### 6. Contradiction inside the same finding set
Findings 15 and 16 state that reading/replying to PR bot comments has **zero
task/module backing** (#462 OPEN, and #462 does not even cover posting).
Finding 17 faults `kb-session-reflect`'s "work a mise task already owns"
section for not flagging exactly that work. Both cannot hold: if no task owns
it, that section is unable to fire by construction. The correct owner of
"a program written twice" is `kb-distill`, which ran in the same tool call.

## VERDICT: REFUTED
The observation (no gh-api row) is real; the stated CAUSE is false, and the
part of the output quoted as evidence is produced by a different mechanism
than the one blamed. The genuine, narrower gap: `report.repeats` counts whole
Bash COMMANDS (`MIN_RUN = 2`), so a structure repeated *inside* one command —
here a `reply()` shell function invoked 8x in a single call — is invisible;
and `DEFAULT_SESSION_LIMIT = 1` scans one transcript only.
