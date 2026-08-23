# Refutation lane — "Three SIXTH ADDENDUM items remain completely untriaged"

Commit context: branch `repowise-mcp-0821`, HEAD at time of probe — see `git rev-parse HEAD`.
Date of probing: 2026-08-22.

## Verdict: REFUTED

The claim fails on three independent counts.

## 1. Item (1) is NOT a SIXTH ADDENDUM item — it is FIFTH

`docs/direction/2026-08-19-ray-directives.md`:
- FIFTH ADDENDUM spans lines 202–274; the dbos / pg_durable bullet is at **:264–268**
  (`> - update workflow to a workflow engine using a state machine library` / `>     - dbos with sqlite or postgres` / `>     - https://github.com/microsoft/pg_durable`).
- SIXTH ADDENDUM begins at **:275**. `sed -n 275,339p` contains no `dbos`, no `pg_durable`,
  no "state machine".
- Repo-wide: `grep -rn "dbos\|pg_durable" docs/direction/` → only :266, :267 (both FIFTH).

The repo's own committed audit agrees and attributes it to a *Ray message*, not to the A6 table:
`docs/research/reports/2026-08-21-session-review-completeness.md:158` places it in **GAP-5**
(Ray messages), row `773421d1 m4`, whereas the SIXTH ADDENDUM table (A6-01..A6-16) is at :101–129
and has no such row.

## 2. Item (1) is not "untriaged research" — the research already exists in the corpus

`sources/media/autonomous-execution-program-20260719.md:83-86` is a researched comparison that names
**both** targets by name:
- ":83 … **Standout: DBOS Transact (1.5k★)** — pip lib, durable `@workflow`/queues/scheduling,
  **backend-agnostic (Postgres OR SQLite since 2026-06)** … Microsoft `pg_durable` (2.7k★, in-DB
  durable exec, OSS 2026-06)."
- ":86 DECISION PENDING: DBOS-on-SQLite … vs DBOS-on-containerized-Postgres now".

It is also *extracted into the graph*: `sources/extractions/framework-design-docs.json:312-320`
(`autonomous_bible_dbos_bridge`), `:895-903` (`framework_plan_dbos_graduation_path`), plus edges at
`:1630`, `:2117`, `:2296`. Dated 2026-07-19 — a month before Ray's ask.

What IS true: no GitHub issue exists. `grep -niE "dbos|pg_durable|state machine|workflow engine"`
over all 302 issue bodies → **0**. Control arm, same file/command shape: `antigravity-cli` → 25,
`currency` → 239. So the negative is armed and real — but it is "unfiled", not "untriaged", and
the research it asks for was already done and ingested.

## 3. Items (2) and (3) ARE triaged, in tracked artifacts

### Item (2) — eliminate currency.toml in favour of mise.toml/pyproject.toml

`docs/research/reports/2026-08-21-session-review-completeness.md:114` (TRACKED — `git ls-files`
succeeds; landed in `8929d47f`, "graphify corpus 0947 (#422)"):

| "get rid of currency.toml … just rely on mise.toml/pyproject.toml" | A6-08 | ✅ F15 + #393 |

F15 (`.agent/kb/reports/agents/2026-08-21-session-review/SYNTHESIS.md:640ff`) carries the actual
measurement:

> Of `currency.toml`'s 15 `[tool.*]` sections, 12 map onto an existing `mise.toml`/`pyproject.toml`
> pin; three do not: `[tool.mise]` (mise is absent from its own registry — control-armed),
> `[tool.claude-code]` …, and `[tool.skillopt]` … Fold this 3-item residue into **#393** …
> the collapse goal itself is already #393/#381/#357.

Filed issues it maps to:
- **#393** OPEN 2026-08-19T20:50:41Z — "mise.toml and pyproject.toml must be the MASTER source of
  every dependency version…" (filed the SAME DAY as the addendum)
- **#381** OPEN 2026-08-19 — hand-editing mise.toml/pyproject.toml → require the owning command
- **#357** OPEN 2026-08-18 — currency roster

That is analysed (12/15 measured), probed (control-armed), and filed. "Completely untriaged" is false.

### Item (3) — antigravity-cli as a graphify source + currency

- `currency.toml:1700-1738` — a live `[tool.antigravity-cli]` block with
  `github = "google-antigravity/antigravity-cli"`, `binary = "agy"`, a measured `version_pattern`,
  and an explicit **recorded decision** on the manifest half:
  > "`manifest` is deliberately absent for now: there is no `sources/antigravity-cli.manifest`, and
  > declaring one before the source is pinned would report DRIFT against a file that does not exist …
  > Add both together."
  Added `d937841d` 2026-08-19 ("currency sweep 2026 08 18 (#375)").
- The completeness report row A6-13 marks it **PARTIAL**, naming exactly which halves are missing
  (source-sync/release-notes protocol, CLI-args) — the opposite of "not analysed".
- **#447** OPEN 2026-08-22 — "Tool resync: antigravity-cli 1.1.18, and claude-code 2.1.239
  (manifest + currency)" names `sources/antigravity-cli.manifest` at body line 120.

The finding's evidence cites #446 and concludes the item is uncovered. #446 is about
`mar3co/fable-orchestrator` + `yuting0624/antigravity-for-claude-code`. The probe stopped at #446
and never reached **#447**, which is the issue for `google-antigravity/antigravity-cli`.
`awk '/^=== #/{h=$0} /antigravity-cli\.manifest/{print h}'` over all bodies → **#447 only**.

## 4. The "re-asked verbatim" causal claim is unsupported

`gh issue view 443/444` — both bodies open `Ray, 2026-08-22 (verbatim):` and neither mentions
2026-08-19, a broken promise, or a repeat ask. For **semantic versioning**, the 2026-08-21
completeness report marks A6-16 **✅ F8**, i.e. it WAS collected and represented; F8's own title
(`SYNTHESIS.md:513`) says "unimplemented and unfiled" — unfiled ≠ untriaged. For **profiling**,
A6-12 is correctly marked ❌ ABSENT/unfiled. So the "two siblings" are not the same case, and the
"because … the promise was never kept" is an inference, not a probe result.

## 5. What survives

- No GitHub issue exists for the dbos/pg_durable ask (armed negative, above).
- No `sources/antigravity-cli.manifest` exists (armed: 73 manifests exist, `antigravity-plugin-cc-*`
  and `fable-orchestrator` manifests present; `grep -ril antigravity-cli sources/*.manifest` → rc=1).
- A6-12 (profiling) was genuinely unfiled until #443 today.

That is a narrower, true finding: **"three asks are unFILED as issues"** — not "untriaged", and not
all three from the SIXTH ADDENDUM.

## Contradiction with another finding in this round's set

Finding 10 (#446 "Neither is in the corpus") is adjacent but not contradictory — different repos.
No other listed finding asserts the SIXTH ADDENDUM was triaged, so this refutation rests on the
repo's own committed audit rather than on a peer finding.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issue bodies #357 #381 #393 #415 #443 #444 #446 #447, and the tracked direction/report files.
