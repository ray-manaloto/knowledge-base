# Refutation lane: bot-reviews finding — graphify-labs' "28 more findings"

Claim: 28 extra findings exist beyond the 8 inline comments, were never fetched
or dispositioned, and are "not reachable via any tool available here"
(annotations_count 0, details_url = graphify.com marketing homepage).

## Verified TRUE so far

- Review body text (review 5001534143) final line, verbatim:
  `· 8 grounded finding(s) anchored inline below; 28 more finding(s) on lines outside this diff (see the check run).`
- Check runs on the three PR-463 head commits:
  - `Graphify` 97131237742 → annotations_count **0**, details_url `https://graphify.com`
  - `Graphify Formal Verification` 97130383684 → annotations_count 0, details_url `https://graphify.com`
  - CONTROL ARM: `Repowise / code health` 97129707431 → annotations_count **7**,
    details_url `https://repowise.dev/pr/ray-manaloto/knowledge-base/463?src=check-run`.
    So the annotations probe DISCRIMINATES; 0 is a real 0.
- `check-runs/97131237742 --jq '.output.text'` (3377 chars) is byte-for-byte the
  same markdown as the review body. It does NOT enumerate the 28.

## Where the finding overreaches

- The review body ITSELF partly characterises the 28, at line 43 of the body:
  `- …and 28 more — each is listed as a finding` — inside the **coupling
  hotspot** list. So the 28 are new-function coupling hotspots (callers/callees),
  not an unknown finding class. The original probe (`--jq .body | tail`) read the
  last line only and missed this.
- TWO graphify-labs reviews exist (5001534143 @ 85201adb, 5001588903 @ later
  head), each saying "28 more". The finding cites one. 16 inline comments total,
  8 per review, duplicated.
- The 8 hotspots named in the body (`_stage_real`, `verify_plan`, `preflight`,
  `plan_source`, `_inventory`, `_verify_staged_destination`, `_record_with_source`,
  `build`) do NOT match the 8 inline comments (`_effective_config`, `plan_source`,
  `_stage_plan_context`, `corpus_main`, `_record_with_source`, `execute`,
  `_stage_real`, `test_a_chunk_whose_argv...`). Only 3 overlap.
- **`.mcp.json` registers a HOSTED graphify MCP** (`https://api.graphify.com/mcp`)
  and this session's MCP instructions advertise it as answering "trace calls or
  callers, assess the blast radius of a change". That is exactly the data class of
  the 28. "not reachable via ANY tool available here" is therefore unproven.


## The probe that produces the OPPOSITE answer

`gh issue view 450 --repo ray-manaloto/knowledge-base --json body` — issue #450,
**re-measured 2026-08-22** ("not carried"), states verbatim:

> `list_repositories` returns a **workspace of two repositories**, both `queryable: true`:
> | `ray-manaloto/knowledge-base` | 10,497 |
> | `ray-manaloto/dotfiles` | 7,776 |
> **23 tools** load as `mcp__graphify__*`. `claude mcp list` → `✔ Connected`.

and, in its own disposition list:

> **remove now** — accepting that `kb-build` is red, so this is the only MCP route to
> a graph of **this repo's own code** until #397/#417 land.

So a hosted graphify MCP indexing THIS repository, 23 tools, `✔ Connected`, was live
in the session. Its advertised surface is exactly the data class of the 28
("trace calls or callers, assess the blast radius of a change"). The 28 are
coupling hotspots — new functions with caller/callee fan-out — per the review
body's own line 43.

**Where the misreading came from:** CLAUDE.md invariant 4 says the hosted graphify
is "a 2-repo workspace, **not** this corpus (#450)". "not this corpus" means not
the ingested `graphify-out/` corpus graph — it does NOT mean "not this repo".
#450 measures knowledge-base at 10,497 nodes, queryable.

## Control arms run

- annotations ENDPOINT (not just the count field), every graphify-labs check run on
  every PR-463 commit → `0`; CONTROL `Repowise / code health` 97129707431 → `7` rows,
  first = `{"path":"python/src/kb_setup/graphify_semantic_corpus_record.py","start_line":427,"title":"Introduced: large method"}`.
  The endpoint discriminates, so the 0 is real.
- `curl -s https://graphify.com | grep -io '<title>...'` →
  `<title>Graphify · the code knowledge graph for AI coding assistants</title>` —
  marketing homepage confirmed.
- `gh api repos/.../comments --jq length` → 0 commit comments (route closed).
- Unauthenticated `curl -X POST https://api.graphify.com/mcp` → **HTTP 401** with
  `www-authenticate: Bearer` — I cannot reach it from bash, which is why #450's
  own measurement (taken from inside a session that CAN) is the load-bearing arm.

## Verdict

**REFUTED** on the load-bearing clause. (a) "review states 28 more" TRUE,
(b) "never fetched or dispositioned" TRUE, (d) "annotations_count 0 / details_url
is the marketing homepage" TRUE and control-armed. (c) "**not reachable via any
tool available here**" is FALSE: a connected, 23-tool graphify MCP indexing this
repo was available all session and was never asked. The finding's own probe stopped
at two fields of one check run and never enumerated the other routes.
