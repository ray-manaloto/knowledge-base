# Refutation lane — "Graph-first rule systematically violated"

CLAIM: all sessions relied on direct source reads instead of querying the graph first.
EVIDENCE OFFERED: 49e2cc30 0/124 (0%), 52f5798a 1/132, 6b974f05 2/217, fb633adf 1/92,
f1d1c0cf 2/34; "measured via grep -c '\"command\":\".*mise run kb-query' and manual
Bash command categorization".

## Probe 1 — reproduce the finding's OWN stated grep (numerator)

    cd ~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base
    for f in 49e2cc30 52f5798a 6b974f05 fb633adf f1d1c0cf; do
      printf "%s literal-grep=" $f; grep -c '"command":".*mise run kb-query' ${f}*.jsonl; done

    49e2cc30 literal-grep=1
    52f5798a literal-grep=1
    6b974f05 literal-grep=2
    fb633adf literal-grep=1
    f1d1c0cf literal-grep=2

The finding reports **0** for 49e2cc30. Its own probe returns **1**. The session's
query is chained: `git status --short && git log --oneline -3 && echo "---" && mise run
kb-query -- "semantic corpus runner merge chunks into aggregate graph" 2>&1 | head -40`.
So "0/124 (0%)" is contradicted by the command the finding says produced it.

## Probe 2 — denominators are not reproducible

JSON-parsed count of Bash tool_use blocks (unique tool_use ids, no compaction dupes):

    49e2cc30 bash_blocks=272 unique_ids=272 unique_cmds=263
    52f5798a bash_blocks=299 unique_ids=299 unique_cmds=292
    6b974f05 bash_blocks=379 unique_ids=379 unique_cmds=371
    fb633adf bash_blocks=168 unique_ids=168 unique_cmds=168
    f1d1c0cf bash_blocks=78  unique_ids=78  unique_cmds=75

Finding's denominators: 124, 132, 217, 92, 34. Ratios to the measured counts are
0.46 / 0.44 / 0.57 / 0.55 / 0.44 — not a constant, so no single omitted class
explains them. `grep -c '"name":"Bash"'` gives 272/299/379/168/78 too. The
denominator came from "manual Bash command categorization", which is a probe with
no control arm and no reproducible definition.

## Probe 3 — the metric measures something the rule never required

The rule is a ONE-TIME PER-SESSION toll, not a ratio. Primary artifact,
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/graph_first.py`:

- :107 — "Then this search is unblocked for the rest of the session."
- :144 `has_queried()` / :155 `note_query()` — a single marker file
  `.agent/state/graph-first/<session_id>.queried`; "That key IS the invalidation
  rule and is why no TTL exists."

So compliance = "did ONE graph query precede the first broad source search". A
queries/all-Bash-commands ratio can never reach a passing value (1.0 would mean
every git/gh/pytest/edit command was a query), so the finding's metric is a probe
that can only return "violation" — no control arm exists for it.

## Probe 4 — replay each session through the repo's OWN detector

`kb_setup.graph_first.decide()` replayed over every Bash/Grep tool_use in
transcript order, `queried` driven by `_GRAPH_QUERY` exactly as the live hook does.

    control DENY  : decide("Bash",{"command":"rg decide python/"},queried=False) -> "Query the graph before searching the tree..."
    control ALLOW : same, queried=True -> None
    control ALLOW2: decide("Bash",{"command":"cat README.md"},queried=False) -> None

    49e2cc30: events=272 first_graph_query_at=2  VIOLATIONS=0
    52f5798a: events=299 first_graph_query_at=55 VIOLATIONS=1
    6b974f05: events=379 first_graph_query_at=5  VIOLATIONS=0
    fb633adf: events=168 first_graph_query_at=4  VIOLATIONS=1
    f1d1c0cf: events=80  first_graph_query_at=4  VIOLATIONS=0

2 violations across 1,198 search/Bash events in 5 sessions. 5/5 sessions queried
the graph; 4/5 within their first 5 commands.

## Probe 5 — cross-check against the LIVE guard's own firings (second route)

    grep -c 'Query the graph before searching the tree' <session>.jsonl
    49e2cc30=0  52f5798a=1  6b974f05=0  fb633adf=1  f1d1c0cf=0
    control (term known present): 'kb_setup' -> 49e2cc30=285, 52f5798a=391

Two independent routes agree exactly (0/1/0/1/0). And BOTH denials were complied
with immediately:

- fb633adf L65 deny -> L70 `mise run kb-query -- "how is the graphify version pin recorded and checked for currency?"`
- 52f5798a L686 deny -> L688 `mise run kb-query -- "how does the corpus authority record bind a plan to the code that will run it?"`

Both denied commands are also the guard's known false-positive class, not
orientation: `grep -rn "0\.9\.4[456]" mise.toml pyproject.toml currency.toml
sources/graphify.manifest 2>/dev/null` (four NAMED files; the `2>/dev/null`
redirect token is parsed as an unresolvable path) and `git grep -n
'^<<<<<<<\|^>>>>>>>' -- '*.py'` (a merge-conflict-marker check).

## Probe 6 — token-spelling bound in the numerator

`_GRAPH_QUERY` (graph_first.py:71) counts `graphify explain|path|god-nodes` as
graph queries, and CLAUDE.md allows them direct. The finding's grep sees only
`mise run kb-query`:

    f1d1c0cf: kb-query=2  graphify explain/path/god-nodes=2   (finding reported 2, actual 4)

## VERDICT: REFUTED

