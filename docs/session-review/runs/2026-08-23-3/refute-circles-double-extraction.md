# Refutation lane: "the 618-line doc was extracted twice and the better chunk was thrown away"

Judged finding: lane `circles`, item 2. Transcript under review:
`/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/672f23a4-61dc-4e30-af59-21a860699ed6.jsonl`
(2,480 records). All transcript timestamps below are UTC (`Z`), file mtimes are local (UTC-5).

## Verdict: REFUTED — headline true, two of the offered evidence clauses are false

The double-extraction core is independently verified. Two named supporting
clauses do not survive primary-artifact probing, and one of them is the
finding's stated *cause*.

## What VERIFIED (independent of the round's self-report)

Every number was re-derived from the chunk files themselves, not from the
transcript's prose:

```
AGENT nodes 111 edges 208 hyper 3
COMMITTED guide nodes 97 edges 112
overlap ids 3 ['..._fnox_check_if_missing_error', '..._suspect_stale_mise_env_cache', '..._unexplored_fnox_surface']
```
(`uv run python` over `$SP/chunk-dotfiles-secrets-guide.AGENT-VERSION.json` and
`sources/extractions/dotfiles-secrets-docs.json`.)

- `wc -l sources/media/dotfiles-secrets-guide.md` = **618**.
- 5 `kb-extraction-worker` Agent dispatches, at 20:47:25 / 20:47:33 / 20:47:47 and
  21:56:02 / 21:56:26. Confirmed by `jq` over the transcript.
- The round's only `Workflow` call is `2026-08-22T13:54:42Z` — i.e. *today's*
  session-review, not part of the round. `.claude/workflows/kb-extract.js` exists,
  16,389 bytes, mtime Aug 13 16:32. **Clause verified.**
- Race timing verified: `kb-merge` of the inline chunk ran at `21:11:21Z`; the
  agent's file landed at 16:30:53 local = `21:30:53Z`. `md5` of
  `chunk-dotfiles-secrets-guide.json` and `...AGENT-VERSION.json` are IDENTICAL
  (`9d529a3208191fef4fed8db60ef8fc50`) — the agent overwrote the inline chunk on
  disk after the merge, exactly as the round reported.

## REFUTED clause 1 — "the chunks were already on disk"

Offered evidence: *"three SendMessage 'no chunk file has appeared' nudges at
20:50:37/41/43, all three answered 'this crossed with my completion' — the chunks
were already on disk."*

The round's **own probe 17 seconds earlier** says otherwise:

```
2026-08-21T20:50:20.539Z  ls -la "$SP" 2>/dev/null | grep -i chunk || echo "no chunks yet"
2026-08-21T20:50:20.700Z  tool_result: no chunks yet
```

And the three agents' completion messages arrive **after** the nudges:

| agent | nudge sent | first completion/"crossed" reply |
|---|---|---|
| extract-secrets-rule | 20:50:41 | 20:54:45 (+4 min) |
| extract-secrets-evidence | 20:50:43 | 21:04:35 / "crossed in transit" 21:05:55 (+15 min) |
| extract-secrets-guide | 20:50:37 | **21:31:37 (+41 min)** |

All three subagents *claimed* they had crossed; none of them had. The finding
adopted three subagents' false self-reports as fact without checking them against
the session's own `ls`. The nudges were not a "cheaper repeat" of a wasted probe —
at the moment they were sent, zero chunks existed.

## REFUTED clause 2 — "graphify has no delete verb, so the denser chunk COULD NOT be merged"

This repo's merge preflight has a first-class supersession path, and the tool
prints it verbatim as the remedy. `kb_setup.chunks.collision_issues` on the agent
chunk against the 27 committed chunks:

```
undeclared supersession: chunk-dotfiles-secrets-guide.AGENT-VERSION.json and
dotfiles-secrets-docs.json both claim source_file
'sources/media/dotfiles-secrets-guide.md'; this merge makes
chunk-dotfiles-secrets-guide.AGENT-VERSION.json own it and DELETES the other(s)'
nodes for that file. If that is intended, add
'sources/media/dotfiles-secrets-guide.md' to ...'s 'supersedes' list
```

**Control arms (the probe discriminates):**
- CONTROL A — same chunk with `source_file` rewritten to a novel path → **0** issues.
- CONTROL B — same chunk with `supersedes: ["sources/media/dotfiles-secrets-guide.md"]`
  → **0** issues.

So the "permanent 205-node double representation" the round feared, and the
"no delete verb ⇒ could not be merged" the finding repeats, are both wrong:
`build_merge` deletes the replay loser's nodes for a superseded `source_file`
(`python/src/kb_setup/graphify_ops.py:154-160`). The swap was available; nobody
looked. The *conclusion* (chunk not merged) is true; the stated *mechanism* is false,
and the false mechanism is what makes the loss read as unavoidable.

## UNESTABLISHED — "the better extraction"

"Better" rests entirely on edges/node (1.87 vs 1.15). The round's own commit
argues the opposite on the metric that matters to retrieval: *"Claim-style is also
what makes `kb-query --idf` rank these at all — it scores node LABELS."* No probe
in the round or the finding compares retrieval on the two chunks. Also, the chunk
was not "thrown away": it is preserved at
`$SP/chunk-dotfiles-secrets-guide.AGENT-VERSION.json` (verified present, 139,190 B).

## One clause that is STRONGER than the finding claims

`.claude/workflows/kb-extract.js:276` is `const results = await parallel(...)` —
the sanctioned fan-out **blocks until every agent returns**. Using it would have
made the inline duplicate extraction structurally impossible. (It contains no
timeout knob at all — `grep -c timeout` = 0; control: `grep -c "agent("` = 2, so
the file was read.) The round's stated lesson ("a fan-out timeout should scale
with the unit of work") therefore names a parameter that does not exist in the
mechanism it skipped; the real lesson is "use the blocking workflow".

## Contradictions with other findings in the set

None found. Finding 3's "+11 anchor shift in a completed 42-node chunk" matches the
rule chunk (42/59/3, reply 20:54:45) and is consistent. Finding 13's "7 heredoc
edits against docs/secrets.md" and finding 14's "validate-chunks never checks line
numbers" are both corroborated by the same commit body.

## GitHub repos touched

_None._
