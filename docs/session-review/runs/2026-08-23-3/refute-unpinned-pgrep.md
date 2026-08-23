# Refutation probe — "pgrep for codex process liveness used 7 times"

Session under review: `6ae19ff6-2b88-4aea-8fa7-c0430395e2da` (2026-08-21, 06:08:40Z→…),
transcript `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/6ae19ff6-2b88-4aea-8fa7-c0430395e2da.jsonl`.

## Verdict: REFUTED as written (the count belongs to a different token)

### Probe
```
jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use" and .name=="Bash") | (.input.command|gsub("\n";" ⏎ "))' $F \
  | awk '{printf "%d\t%s\n", NR-1, $0}' | grep -E 'pgrep|ps -'
```
Returns exactly the 7 indices the finding cites — 39, 40, 49, 56, 70, 81, 82 —
but only **2 of them contain `pgrep`** (39 and 40). The other five are
`ps -axo`/`ps -o` invocations.

Broader arm (any tool, whole file):
```
jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | "\(.name)\t\((.input|tostring))"' $F | grep -c pgrep
=> 2      (both Bash)
```
Raw line grep `grep -c pgrep $F` => 4 (2 tool_use + 2 tool_result echoes).

### Control arms (the probe can return larger numbers)
- same extraction, `grep -c 'codex exec'` over all tool_use inputs => **8**
- same extraction, `grep -cE 'pgrep|ps -'` => **7**
- `jq … | .name | sort | uniq -c` => `102 Bash, 20 Agent, 1 ListAgents` (so it sees the whole tool stream)
So the extraction is not systematically empty; 2 is a real 2.

### What the 7 actually are
| idx | probe | what it is |
|---|---|---|
| 39 | `pgrep -fl 'codex exec' \| grep -v -i chatgpt` | pgrep codex-liveness (the one true instance) |
| 40 | `ps -o … -p 63983; pgrep -P 63983; ps -axo … grep -i codex` | follow-up on the pid 39 found; result showed the pid gone, only `otelcol-contrib` + `SkyComputerUseService` left |
| 49,56,70,81 | `ps -axo pid,etime,command \| grep -E 'codex exec\|codex-companion'` | the byte-identical round-preflight chain (finding 17) — **ps, not pgrep** |
| 82 | `ps -o pid,ppid,… -p 65731` + parent chain + `lsof -d cwd` | identity walk on a stray pid; result: `/Applications/ChatGPT.app/…/codex exec … Codex Skysight`, parent `ChatGPT.app`. Disambiguating ChatGPT.app's bundled codex — i.e. the control-arm the lesson asks for, not a liveness poll |

### The substance that DOES survive
- Codex lanes were Agent-tool teammates (`fable-orchestrator:codex-implementer`
  codex-lane1/2/3 + r2), so `ListAgents` is the authority per
  `subagent-liveness-comes-from-listagents.md` ("for anything spawned with the
  Agent tool, liveness comes from ListAgents … never from pgrep, `ps`").
- `ListAgents` was called **1** time against **20** Agent spawns and 7 process probes.
- The cited enforcement analogy checks out against the primary artifact:
  `memory/i-violate-standing-directives-at-scale.md` — "The bare-interpreter
  count went 62 → 0 once `hook_guard` denied it. The graph-first hook only
  prints, and scored 0/19."
  (Note MEMORY.md's summary line renders the same figure as `62→1`, not 62→0 —
  the repo disagrees with itself on that digit.)

### Contradiction with another live finding
Finding **6** states "**7 pgrep/ps** codex-liveness probes against 1 ListAgents".
That is the accurate attribution of the same 7 commands. Finding **16** re-spells
the same 7 as pgrep alone. Same fact, two probes, one token wrong — the defect is
in finding 16's wording, and it is exactly the token-spelling bound class.
