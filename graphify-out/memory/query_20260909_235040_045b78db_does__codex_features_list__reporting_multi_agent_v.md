---
type: "query"
date: "2026-09-09T23:50:40.520539+00:00"
question: "Does 'codex features list' reporting multi_agent_v2 false mean this machine runs multi-agent V1?"
contributor: "graphify"
outcome: "corrected"
correction: "A control arm proves a probe discriminates FOR THE QUESTION THAT PROBE ASKS —\nnever for the question you wanted answered.\n\nI reported that this machine runs codex multi-agent V1, from `codex features\nlist` showing `multi_agent_v2  stable  false`. I measured it myself and\ncontrol-armed it by running from the repo root AND `/private/tmp`, identical\nboth times. The measurement was correct. The conclusion was wrong.\n\n`codex features list` (`cli/src/main.rs:1769-1795`) prints raw feature booleans\nand NEVER calls `multi_agent_version_for_model` — 0 hits in that code path.\nThree resolvers exist in `config/mod.rs`: `:1533` flags only, `:1543` flags plus\nthe Collab fallback (what the CLI prints), and `:1553`\n`multi_agent_version_for_model`, which falls through to THE MODEL'S OWN CATALOG\nTAG and is what a real session calls (`turn_context.rs:949`, cached once per\nsession in a `OnceLock`).\n\n`models.json` tags gpt-6-astra and gpt-5.6-sol BOTH as `\"v2\"`. The root model\nhere is astra; the subagent default is sol. V2 has been running the whole time.\nConfirmed by live observation afterwards: the spawn tool in the rollout JSONL is\nnamed `spawn_agent`, a V2 name — V1's are `spawn`/`wait`/`send_input`/\n`close_agent`/`resume_agent`.\n\nMy control arm answered \"is this flag state caused by project config?\" — true,\nand irrelevant. Before trusting a probe, ask what question its CODE PATH can\nactually answer, not merely whether it discriminates.\n\nCorroboration already sat in our own corpus, unread: the vendored\n`codex-orchestration` doc says *\"Sol and Terra already select v2 ... Do not add\n`enabled = true` for a Sol or Terra root.\"*\n"
---

# Q: Does 'codex features list' reporting multi_agent_v2 false mean this machine runs multi-agent V1?

## Answer

Seven values are stale at the graphify 0.9.57 pin, not the six #728 names.
Three were on no list: `detected_count` (471) and `extracted_count` (463), both
derived at v0.9.53 with 19 files added since; and the disposition catalog's
`uv.lock` entry, whose bytes moved (`c2e5f129…`/1015646 -> `cd961937…`/1015799).

Five of the seven derive with ZERO graphify involvement, correcting #740's
stated order: `source_manifest()` (`graphify_baseline.py:583`) is pure
git+worktree and runs at `:1798`, BEFORE `detect_checked:1809`. Only the two
COUNTS need a build.

The derivation is PROVEN and control-armed: re-running it against the OLD pin's
inputs reproduces the accepted `2a1f353a5d6ee0f087744197e56d07a8f2bcbf84bb048cfd6c8b281821bf5ac0`
exactly — the value a real 0.9.53 build produced. So the encoding
(`msgspec.json.encode(x) + b"\n"`, per `_write_json:1388-1391`) is right and the
new-pin candidates are real candidates, not artefacts.

The generalisable finding: a hand-written enumeration of DERIVED values is wrong
every time. Round f found #728's 2-value list wrong (it was 6); this round found
the 6-value list wrong (it is 7). The primitive must DERIVE the set, never read
a list.


## Outcome

- Signal: corrected
- Correction: A control arm proves a probe discriminates FOR THE QUESTION THAT PROBE ASKS —
never for the question you wanted answered.

I reported that this machine runs codex multi-agent V1, from `codex features
list` showing `multi_agent_v2  stable  false`. I measured it myself and
control-armed it by running from the repo root AND `/private/tmp`, identical
both times. The measurement was correct. The conclusion was wrong.

`codex features list` (`cli/src/main.rs:1769-1795`) prints raw feature booleans
and NEVER calls `multi_agent_version_for_model` — 0 hits in that code path.
Three resolvers exist in `config/mod.rs`: `:1533` flags only, `:1543` flags plus
the Collab fallback (what the CLI prints), and `:1553`
`multi_agent_version_for_model`, which falls through to THE MODEL'S OWN CATALOG
TAG and is what a real session calls (`turn_context.rs:949`, cached once per
session in a `OnceLock`).

`models.json` tags gpt-6-astra and gpt-5.6-sol BOTH as `"v2"`. The root model
here is astra; the subagent default is sol. V2 has been running the whole time.
Confirmed by live observation afterwards: the spawn tool in the rollout JSONL is
named `spawn_agent`, a V2 name — V1's are `spawn`/`wait`/`send_input`/
`close_agent`/`resume_agent`.

My control arm answered "is this flag state caused by project config?" — true,
and irrelevant. Before trusting a probe, ask what question its CODE PATH can
actually answer, not merely whether it discriminates.

Corroboration already sat in our own corpus, unread: the vendored
`codex-orchestration` doc says *"Sol and Terra already select v2 ... Do not add
`enabled = true` for a Sol or Terra root."*
