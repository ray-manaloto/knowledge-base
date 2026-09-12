# LEAD REPORT — extracting issue 91870 into the corpus (Tracks A + B)

Lead: `kb-codex-astra-advisor`. Date **2026-09-12**. Fan-out per Ray's directive.

## How the work was actually split, and why

| lane | model / effort | sandbox | status |
|---|---|---|---|
| **A1** — `gh`'s Go source at the v2.98.0 pin | `gpt-5.6-sol` / `xhigh` | read-only | **DONE rc=0** |
| **B1** — graphify extension points | `gpt-6-astra` / `xhigh` | read-only | **DONE rc=0** |
| **B2** — graphify ingest / URL paths | `gpt-6-astra` / `xhigh` | read-only | **DONE rc=0** |
| **Track A live probes** | run by the lead in-session | — | **DONE** |

🔴 **Track A's empirical half could not be delegated to a codex lane.** A codex
`--sandbox read-only` lane has **no network egress** — `network_access` is a
`sandbox_workspace_write` key and does nothing under read-only, and this lane
type is forbidden `--write`/`--network` by its own spec. So every `gh`/`curl`
probe was run in-session, and a companion lane (A1) read gh's Go source at the
pin to answer the mechanism questions without network. The two halves agree
everywhere they overlap and each caught something the other could not.

Reports on disk, all verbatim at receipt:

- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-a-live.md` — Track A live, 15 findings
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-a1-gh-source.md` — lane A1 verbatim
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b1-extension-points.md` — lane B1 verbatim
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/reports/agents/extract-research-b2-ingest-paths.md` — lane B2 verbatim

---

## 1. THE DECISION THIS INFORMS — one sentence per track

**Track A.** Pull the issue with **`gh issue view --json body,comments,…`** (the
only route that returns all 161 comments without flag gymnastics) plus
**`gh api .../timeline --paginate`** for the 23 cross-references and the one
deleted comment, then fetch the 22 attachments with `gh api <durable URL>`;
three other obvious commands silently return 30, 100, or "all but the hidden
ones", every one of them rc 0.

**Track B.** **Do not carry a second fork patch** — graphify exposes no URL/media
handler registration, and patching `_detect_url_type` would fix only 1 of the 22
assets anyway, so download locally and feed `kb-transcribe` plus extraction
chunks.

---

## 2. TRACK A — the capability table

Every row's control arm was run in the same minute at a measured rate-limit
budget (`core` 4903→4899 of 5000, `graphql` 5000/5000), so **no zero below is a
rate limit**.

| route | what it UNIQUELY gives | what it MISSES | control arm run |
|---|---|---|---|
| `gh issue view --json comments` | **All 161 comments with no `--paginate`** — gh's own preloader loops `comments(first:100, after:$endCursor)` until `hasNextPage` is false (`pkg/cmd/issue/view/view.go:152`, `pkg/cmd/issue/view/http.go:11-53`). Also `minimizedReason`, `includesCreatedEdit`, `viewerDidAuthor` | no timeline, no per-user reactions, **no attachment field** | returned 161 vs authoritative 161; `gh issue list` on the same issue returned 100 |
| `gh api .../issues/{n}` | the authoritative `comments` integer that every other count is checked against; REST-only keys (`issue_field_values`, `pinned_comment`, `sub_issues_summary`) | everything below | `--jq keys` → 34 keys, none attachment-related, while `reactionGroups` etc. do appear in the sibling enumeration |
| `gh api .../comments --paginate` | per-comment **`updated_at`** (edit detection), `performed_via_github_app`, `pin`, inline `reactions` counts, `html_url` | **returns 30 of 161 without `--paginate`, rc 0** | 30 (no flag) vs 161 (flag) vs 161 (authoritative) — same `--jq 'length'` shape produced both |
| `gh api .../timeline --paginate` | **479 entries**: `cross-referenced`×23, `comment_deleted`×1, `referenced`×5, `labeled`×3, `mentioned`×121, `subscribed`×150 | comment bodies are present but the route is 3.4× the bytes | event histogram over all 479; `commented`×161 matches the authoritative count, so the route is complete |
| `gh api .../reactions --paginate` | **per-user reaction attribution** (141 rows of `{content,user,created_at}`); `reactionGroups` gives totals only | comment-level reactions need `/comments/{id}/reactions` | 141 returned = the issue's own `reactions.total_count` of 141 |
| `gh api <durable attachment URL>` | **the asset bytes** — absolute URLs bypass the REST prefix (`pkg/cmd/api/http.go:16-27`) | nothing; it is byte-identical to curl | `cmp` vs curl → IDENTICAL (4,071,679 B); bad uuid → **rc 1**, `gh: HTTP 404`, rc read unpiped |
| `gh issue list --json comments` | nothing we need | **silently caps at 100 per issue, rc 0** — never calls the preloader, and its exporter drops the `pageInfo` that would reveal it | live: 91870 → `comments=100` while `view` → `161` |
| `gh issue view --comments` (non-TTY) | nothing we need | **omits minimized comments entirely** (`pkg/cmd/pr/shared/comments.go:38-50`; gh's own test: 6 comments, 5 rendered) | A1, from source; not re-armed live |
| search indexes (4, separately) | **issues index alone** found `#93215 "Add mods: sec-default, diff and telemetry"` (CLOSED) + 4 more siblings, none of them in the timeline | discussions is **structurally empty** | code 106 / repos 16 / issues 117, `incomplete_results:false`; discussions armed at 28,472 for `claude code` while `has_discussions:false` for the repo |

### The asset inventory — measured, and larger than the brief

**22 distinct URLs, 50.7 MB.** 9 `video/mp4` (46.8 MB), **9 `image/jpeg`**, 1
`image/gif` (3.9 MB), 1 `image/png`, 1 **`image/svg+xml`** (591 KB, and it is
text — directly ingestible as prose), 1 `application/pdf` (8 pages).

Two URL forms, and the difference decides Track B: `…/user-attachments/files/<id>/<name>.pdf`
keeps its extension (1 asset); **`…/user-attachments/assets/<uuid>` has no
extension at all (21 assets)**. Signed redirect targets all carry
`X-Amz-Expires=300` — five minutes. Store the durable URL, never the signed one.

**`curl -I` reads every one of these as 403.** The S3 presigned signature covers
the method, so HEAD is rejected while GET returns 206 + the real `Content-Type`.
Anything probing these with a HEAD request will report a live public asset as
forbidden.

### gh versions — a real "no"

`v2.99.0` (2026-09-01) adds `--attach`: it **uploads** local media to issues/PRs/
comments and rewrites markdown references. Nothing in it reads, lists or
downloads an existing attachment. `v2.100.0` (2026-09-03) adds experimental
`api_host` routing and a `webhook` extension — nothing relevant. **Upgrading gh
does not help us.** One behaviour change does matter: 2.99.0 rejects
`--comments` with `--json`; at our 2.98.0 the pair is accepted and `--comments`
is **silently ignored**. Use `--json comments`, never `--comments --json`.

Rate limits are distinguishable from zeros: an errored page produces `gh: <msg>`
on stderr and `SilentError` → **exit 1** (`pkg/cmdutil/errors.go:35`,
`internal/ghcmd/cmd.go:42-50`). **But gh streams each page to stdout before
requesting the next**, so a mid-`--paginate` failure leaves partial valid JSON
beside a non-zero rc. **The ingestion rule: require rc 0 and discard stdout
entirely on non-zero.** A1 also found a silent rc-0 stop: `findEndCursor`
returns `""` rather than erroring on malformed JSON or a missing `pageInfo`
(`pkg/cmd/api/pagination.go:39-47`).

---

## 3. TRACK B — the straight answer on the fork patch

### Can `_detect_url_type` be fixed WITHOUT patching the fork?

**No sanctioned seam exists — and you do not need one.** B2's verdict, which I
verified against the source myself rather than relaying:

- `ingest(url, target_dir, author, contributor)` at
  `sources/graphify/graphify/ingest.py:219` computes `url_type` internally and
  runs a **fixed if/elif chain** (`:234-255`). No dispatch dict, no `getattr`,
  no parameter, no env var. `"github"` falls to the `else` →
  `_fetch_webpage` → `_fetch_html` → `safe_fetch_text`. Overriding any of it is
  monkeypatching. *(Verified: I read `:216-258` directly.)*
- B2's control arm for that negative: the same probe shape **did** find a real
  registry elsewhere — `resolver_registry.py:48` `def register(resolver)` with
  `run_language_resolvers(..., resolvers=...)` injection. So the absence in
  `ingest.py` is an answer, not a broken search.

🔴 **And a patch would not be worth it anyway.** Reordering the if-chain so
`.pdf` beats `github.com` fixes **1 of 22 assets**. The other 21 are
`assets/<uuid>` with **no extension**, so no extension-based branch can ever
classify them. This is the lead's own measurement meeting B2's source reading,
and neither half implies it alone.

### The failure is silent, not loud — the cross-lane finding

- `security.py:22` — `_MAX_TEXT_BYTES = 10_485_760` (10 MiB), the cap
  `safe_fetch_text` passes down (`:302`).
- `security.py:294` — exceeding it raises `OSError(… exceeds size limit …)`.
- `security.py:308` — **under** it, bytes are `.decode("utf-8", errors="replace")`.
- Measured largest asset: **9,789,851 B = 9.34 MiB**. **All 22 are under the cap.**

So graphify would fetch all 50.7 MB, UTF-8-decode MP4/JPEG/PDF/GIF into
mojibake, markdownify it, keep the first 12,000 characters
(`ingest.py:160` — B2 cited `:144`, which is the `_html_to_markdown` call site;
the slice itself is `:160`), and **raise nothing**. B2 correctly refused to
assert unbounded buffering; only the measured sizes say which side of the cap we
land on.

### Two corrections to the brief's framing of Track B

Both from B2 reading the source, both re-verified by me:

1. **`manifest_ingest.py` parses PACKAGE manifests, not our source manifests.**
   `PACKAGE_MANIFEST_NAMES` at `:28` is exactly `{apm.yml, apm.yaml,
   pyproject.toml, cargo.toml, go.mod, pom.xml}`. It cannot declare a URL, a
   media source, or an explicit type. It is reachable via `graphify extract
   <path>`. **We are leaving nothing on the table here** — it answers a
   different question than our `sources/*.manifest` flow.
2. **`mcp_ingest.py` indexes local MCP *config files*** — neither "ingest from
   an MCP server" nor "expose ingestion as an MCP tool". It reads a local path
   (`:94`), parses `mcpServers`/`mcp.servers`, and emits server/command/args/env
   nodes. **`serve.py`'s handler table is exactly 10 tools** (`:2068-2078`:
   `query_graph, get_node, get_neighbors, get_community, god_nodes, graph_stats,
   shortest_path, list_prs, get_pr_impact, triage_prs`) — **no ingestion or
   transcription endpoint**. So `kb-serve` cannot be an ingestion route.

### The one risk that would change the recommendation

B2 named it and could not test it offline: **`transcribe(url)` has a URL branch
that calls yt-dlp**. `transcribe.py:136` is `if is_url(str(video_path)):
audio_path = download_audio(...)`, and `download_audio` is yt-dlp with
`format: 'bestaudio[ext=m4a]/bestaudio/best'` *(verified by me)*. If yt-dlp's
generic extractor handles a direct `user-attachments` mp4, route (b) would
transcribe the 9 videos from their URLs with no local download step.

**The cheap probe that settles it**: `mise run kb-transcribe -- <one durable
video URL>` against a single 4 MB asset. It is one command and it is the only
open question in Track B. It does not affect the PDF, the SVG or the 12 images,
which need route (c) regardless.

---

## 4. DISAGREEMENTS — not smoothed over

1. **The brief says "9 videos and an architecture PDF"; there are 22 assets.**
   The ten are right. Twelve image assets are unaccounted for, including a
   591 KB **SVG** (text, directly ingestible) and a 3.9 MB **GIF** screen
   recording in a container `transcribe.py`'s `VIDEO_EXTENSIONS` does not list.

2. **The brief's implied failure — "markdownified as HTML" — is right for all
   22, but for a reason the brief did not state and B2 initially bounded
   differently.** B2 wrote the failure as *"wrong output for smaller binaries,
   bounded download failure for oversized ones"*. Correct as source reading;
   with the sizes measured, **every asset is on the silent side**. Neither
   statement is wrong; together they are complete.

3. **I put a false premise in lane A1's own prompt.** I told it the `--json`
   field set is "generated from a struct's field metadata". A1 refuted it: the
   set is **two hand-written slices** concatenated at `api/query_builder.go:314-351`
   (verified — `:314` is `var sharedIssuePRFields = []string{`). Reflection is
   used at export time, not to derive accepted names.

4. **I expected `gh api` could not fetch a non-API URL. It can.** A1 found the
   mechanism in source (`pkg/cmd/api/http.go:16-27`) and correctly marked the
   outcome UNVERIFIED-FROM-SOURCE; the live probe confirmed it downloads the
   binary byte-identically to curl.

5. 🔴 **`mise run kb-recall-work` reported "no prior work" and there are two
   research reports on this exact topic.** My phase-0 run of
   `kb-recall-work -- "function hooks issue 91870 extraction attachments"`
   returned `tracked_files examined 3427 matched 0`, `issues 0`, `plans 0`,
   `artifact_pages 0`. `git grep -ln 91870` returns **3 tracked files**.
   Armed both directions, same command, same minute:

   | query | stems | tracked_files | issues | plans | artifact_pages | branches | memory |
   |---|---|---|---|---|---|---|---|
   | `"function hooks"` | 2 | **410** | **41** | **56** | **15** | 25 | 78 |
   | `"function hooks issue 91870 extraction attachments"` | 6 | **0** | **0** | **0** | **0** | 42 | 204 |

   **The `git grep`-backed probes AND the stems; `branches` and `memory` OR
   them** (they go *up* with more terms). So adding words to be more specific
   silently converts a rich result into a clean-looking `examined 3427 /
   matched 0` — the exact shape that reads as "nobody has done this". This is a
   defect in a tool whose documented promise is that it *"REFUSES rather than
   returning an empty list, so 'no prior work' can never be read as 'the probe
   never ran'"*: it did not return empty, it returned **wrong**, which the
   refusal cannot catch. Worth a ticket.

6. **Prior work exists and partly supersedes this brief's premises.** Two
   committed reports from **2026-09-10** on branch `feat/728-kb-fork-rebase`
   @ `2c792de5f049`:
   - `docs/research/reports/2026-09-10-function-hooks-research.md` (112 lines) —
     already established the mechanism from `mods/README.md` + `mods/sec-default/`,
     confirmed `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, and recorded the corpus gap
     with a control arm. It recorded **154 comments** as of 2026-09-09; today it
     is **161**, so the thread has moved by 7.
   - `docs/research/reports/2026-09-10-github-function-hooks-examples.md` (435
     lines) — the GitHub-as-examples sweep, three-armed, recording
     `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` → **65** code hits. Today the same
     query returns **106**, `incomplete_results:false`. The index has grown ~63%
     in two days.

   Anyone acting on this report should read those two first; they are not
   duplicated here.

---

7. **Three of Track B's file names mislead, and B1 caught all three by reading
   rather than inferring** — which is what the brief asked for and is worth
   recording as an outcome, not a process note:
   - `hooks.py` is **Git** hooks (post-commit/post-checkout + a merge driver),
     not agent hooks. The agent-host hooks live in `install.py`.
   - `LANGUAGE_EXTRACTORS` in `extractors/__init__.py` reads like a plugin
     registry and is an **inactive migration seed** — read nowhere outside its
     own file (control-armed against `_DISPATCH`, which is read three times in
     `extract.py`). Registering into it does nothing.
   - `mcp_ingest.py` / `manifest_ingest.py`, per B2 above.

8. **B1 and B2 never saw each other's work and reached the same conclusion by
   the same control arm.** Both concluded no ingest/URL seam exists; both used
   `resolver_registry.register()` as the positive control proving their search
   could find a registry if one were there. Independent agreement on a negative
   is the strongest form this evidence takes, and it is why the "no second fork
   patch" recommendation is stated without hedging.

---

## 5. WHAT I COULD NOT ESTABLISH

- **Whether `transcribe(url)`/yt-dlp handles a `user-attachments` mp4.** The one
  open Track B question. UNVERIFIED — one `kb-transcribe` call settles it.
- **Whether `gh issue view --json comments` truncates on a much longer thread.**
  161 came back complete in two GraphQL pages; I did not find a ceiling and A1
  found no final cap in `view` (only in `list`). UNVERIFIED above ~161.
- **Whether GitHub ever expresses secondary throttling as HTTP 200 with no
  GraphQL `errors` and no pagination metadata** — which is the one shape that
  would make A1's rc-1 guarantee fail open. A1 flagged it; I did not provoke a
  rate limit to test it. UNVERIFIED.
- **Private-repo attachment behaviour.** All asset probes were unauthenticated
  against a public repo. gh deliberately drops auth across a cross-host redirect
  (`api/http_client.go:151-169`), so a private repo may differ. UNVERIFIED.
- **Transcription itself was never run.** `gh`/`curl` → local `.mp4` is armed
  end-to-end (byte-exact, `file(1)` confirms the container); the whisper step
  was not executed.
- **`gh` 2.99.0/2.100.0 were read from release notes, not from source.** Lane A1
  had no network and correctly declined to guess; I read the API. Neither of us
  read the 2.99.0/2.100.0 code.
- **Lane-environment artifact worth knowing**: this repo's PreToolUse guards fire
  *inside* codex lanes. Both A1 and B2 reported searches denied by the
  graph-first hook, and A1 misread the remedy as "the user-forbidden
  `mise run kb-query`". A read-only research lane cannot satisfy a guard that
  wants a mise task run. This did not change either lane's conclusions, but it
  cost both of them probes.

---

## 6. § B1 — graphify's extension points, and whether any of them fits

Lane B1 returned rc=0 after ~18 min. Verbatim at
`.agent/kb/reports/agents/extract-research-b1-extension-points.md` (403 lines).
It read the source rather than inferring from filenames, and it graded each seam
PUBLIC / INTERNAL / NONE. **I re-verified every load-bearing claim below against
the pinned clone myself.**

### The seams that are real

| seam | file:line | grade | what it would let us do |
|---|---|---|---|
| **Cross-file resolver registration** | `resolver_registry.py:48` `def register(resolver)` → `_REGISTRY` | **PUBLIC** | Register a suffix-gated resolution callable in-process, before extraction. 12 built-ins register this way (`extract.py:4601-4677`). Nothing restricts the callable to graphify modules. |
| **Semantic chunk callback** | `llm.py:2951`, `:3078`, `:3103` | **PUBLIC** | Pass `on_chunk_done(idx, total, result)` when embedding graphify. |
| **Custom LLM providers** | `llm.py:281-318`, `cli.py:1064-1179` | **PUBLIC** | Add named **OpenAI-compatible HTTP** providers via `~/.graphify/providers.json` (project-local needs `GRAPHIFY_ALLOW_LOCAL_PROVIDERS=1`, gated because a repo-local file "controls where your corpus and API key are sent"). |
| **Graph interchange** | `build.py:798`, `:1397`, `:1772`; `cli.py:4740` | **PUBLIC** | Produce extraction dicts/chunks externally, then use graphify's builders and `merge-chunks`. **This is the seam this repo already uses.** |
| `.graphifyignore` · `.graphifyrc` | `detect.py:1196`; `hooks.py:465` | **PUBLIC** | Shape the corpus; set the viz node limit. |
| **~43 `GRAPHIFY_*` env vars** | inventoried with false-positive controls | PUBLIC/INTERNAL | Tune behaviour without patching. Includes the fork's own `GRAPHIFY_OPENAI_CLI_MODEL` (`llm.py:2071`) and `_EFFORT` (`:2115`). |

### The seams that do not exist

| claimed seam | reality | verified |
|---|---|---|
| **Language-extractor registry** | `LANGUAGE_EXTRACTORS` (`extractors/__init__.py:37`) is an **inactive migration seed** — its own docstring says *"wiring dispatch through it is a later, separate step."* Real dispatch is `_DISPATCH`/`_SHEBANG_DISPATCH` via `_get_extractor` (`extract.py:5921`). | ✅ I confirmed `LANGUAGE_EXTRACTORS` is read **nowhere** outside its own file, control-armed against `_DISPATCH`, which IS read at `extract.py:5940/:5963/:5964`. Mutating the "registry" does nothing. |
| **Exporter discovery** | `exporters/base.py` is 14 lines: a docstring, a `__future__` import, and `COMMUNITY_COLORS`. No ABC, no Protocol, no lookup. The CLI checks a fixed 8-format tuple and dispatches with `if/elif`. | ✅ `cli.py:2824` is literally `if subcmd not in ("html","callflow-html","obsidian","wiki","svg","graphml","neo4j","falkordb")`. |
| **Python plugin entry points** | None. `pyproject.toml` has `[project.scripts]` only. No `__subclasses__`, no `pkgutil.iter_modules`, no plugin loader. | ✅ `[project.scripts]` at `pyproject.toml:104`; `grep entry-points` → 0, control-armed against `scripts` → 1 hit. |
| **Overriding a built-in provider** | Impossible through the provider loader: `if name in BACKENDS or name in providers: continue`. | ✅ `llm.py:306`. |

### B1 and B2 agree independently, which is the finding

Neither lane saw the other's work. **Both concluded there is no ingest/URL seam,
and both used `resolver_registry.register()` as the positive control arm proving
their search could find a registry if one existed.** B1 states the decision rule
directly: the public resolver API is the mechanism to evaluate *if* the change is
an additive cross-file resolution pass at the tail phase; **a URL/media handler
is not that**, and for "a new CLI language, a new export format, an earlier
pipeline phase, or a new executable transport" the public seams *do not establish
the capability*.

That last clause also answers a question nobody asked but which matters here:
**the provider seam could not have replaced our `openai-cli` fork patch either.**
It configures OpenAI-compatible HTTP only; the fork's transport has its own
explicit branch at `llm.py:2357-2358`. So the existing patch was necessary, and
the case for a *second* one is weaker, not stronger, than it looked.

### `always_on/` — live here, and it has a bite worth knowing

Six markdown templates, consumed by `install.py` through a cached `_always_on()`
(`install.py:57-79`), written into a host project's instruction files:

```
claude-md.md          -> CLAUDE.md                      (install.py:1766-1781)
claude-md.md          -> CODEBUDDY.md                   (install.py:1955)
agents-md.md          -> AGENTS.md                      (install.py:1530)
gemini-md.md          -> GEMINI.md                      (install.py:742)
vscode-instructions.md-> .github/copilot-instructions.md (install.py:909)
kiro-steering.md      -> .kiro/steering/graphify.md      (install.py:992)
antigravity-rules.md  -> .agents/rules/graphify.md       (install.py:1040)
```

🔴 **`claude_install()` does not append — it REPLACES.** `_replace_or_append_section`
(`install.py:511+`) replaces the section "from that heading to the line before
the next H2", and `claude_install` then `target.write_text(new_content)`
(`install.py:1781`). ✅ Verified by reading both functions.

**So a `graphify install` would overwrite this repo's customised root `CLAUDE.md`
`## graphify` section** — the one carrying our `mise run kb-query` / `kb-watch`
guidance instead of the template's bare `graphify` commands. That is independent
source-level confirmation of `do-not.md` #1 and of why `kb-skill-refresh`
re-applies `currency.skill.ADDENDA` after running the installer. B1 reached it
from graphify's source with no knowledge of our rule.

B1 also separates two things this repo conflates in casual speech: the root
`CLAUDE.md` `## graphify` section descends from `always_on/claude-md.md`, while
`.claude/CLAUDE.md`'s `# graphify` heading comes from a *different* generator,
`_skill_registration()` (`install.py:351-357`), written at `install.py:666-686`.
Two origins, two templates, one installer.

### `hooks.py` is GIT hooks, not agent hooks

Another filename that misleads. `hooks.py:793-820` installs **post-commit and
post-checkout Git hooks** plus a graph merge driver. The agent-host hooks
(Claude/CodeBuddy PreToolUse, Gemini BeforeTool, Codex, OpenCode/Kilo) live in
`install.py:323/742/1477/1395`. Neither is a graphify build-event bus — B1
searched for `pluggy`, `blinker`, `stevedore`, `subscribe`, `emit_event` and
found none, with `on_chunk_done` and the resolver registry as positive controls.

### What B1 explicitly could not establish

- **No runtime validation.** Pure source audit; nothing was executed.
- **API stability across releases is UNVERIFIED** — `register()` is public *at
  this commit*, which is not a compatibility promise.
- **Whole-program discovery absence is not formally proven** — controlled
  lexical probes, not semantic analysis. Its AST cross-check could not run:
  direct `python` was hook-denied, its heredoc could not create a temp file, and
  offline `uv run --no-sync` failed opening the uv cache.
- **It did not read `cli.py` or `extract.py` end to end**, and says so with the
  exact line ranges it did read. An initial whole-file read of
  `extractors/engine.py` was truncated and it explicitly declines to claim it
  read all 6,401 lines.
- Historical authorship of our local Claude blocks is UNVERIFIED — wording and
  destinations match, but no git blame was run.

---

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — the extraction target: issue 91870, its 161 comments, 479 timeline entries, 141 reactions, 22 attachments; plus siblings #93215, #92440, #92533, #92469, #93831 and the `mods/` tree.
- [cli/cli](https://github.com/cli/cli) — `gh` itself; pinned clone at v2.98.0 (`a255baf71d13fe5947a4eb7ad521ffd412d64cee`) read by lane A1, plus v2.99.0/v2.100.0 release notes read from the API.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — our fork, pinned `kb-pin/openai-cli-backend-v0.9.57` @ `3c9b930f386f80c393fe658e1afb685030828c6a`; `ingest.py`, `security.py`, `transcribe.py`, `manifest_ingest.py`, `mcp_ingest.py`, `serve.py`, `resolver_registry.py` read by lanes B1/B2 and re-verified by the lead.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the upstream our fork tracks; named only as the fork's origin, not read this round.
- [ray-amjad/awesome-claude-code-function-hooks](https://github.com/ray-amjad/awesome-claude-code-function-hooks) — curated FH list; corpus candidate.
- [cvuijst/cc-function-hooks-poc](https://github.com/cvuijst/cc-function-hooks-poc) — POC against the 91870 API; corpus candidate.
- [Monte9/claude-function-hooks](https://github.com/Monte9/claude-function-hooks) — reference implementation of the hook algebra; corpus candidate.
- [productowner-ro/claude-function-hooks](https://github.com/productowner-ro/claude-function-hooks) — JS/TS reference; corpus candidate.
- [scriptease/claude-code-redact-plugin](https://github.com/scriptease/claude-code-redact-plugin) — example plugin on functional hooks.
- [fnclaude/hooks](https://github.com/fnclaude/hooks) — typed TS wrapper for hook entry points.
- [AnExiledDev/cc-changelog-plugin](https://github.com/AnExiledDev/cc-changelog-plugin) — repositories-index hit.
- [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) — PR #867 adds a Function Hooks section.
- [yonatangross/orchestkit](https://github.com/yonatangross/orchestkit) — #3917 watch thread, PR #3918 handler policy and gate.
- [lossless-claude/lcm](https://github.com/lossless-claude/lcm) — #376, function-hooks module.
- [Yeachan-Heo/gajae-code](https://github.com/Yeachan-Heo/gajae-code) — #5263, capability-scoped hooks epic.
- [goondocks-co/myco](https://github.com/goondocks-co/myco) — #1111/#1172, hook-surface research.
- [jeremylongshore/tons-of-skills-marketplace](https://github.com/jeremylongshore/tons-of-skills-marketplace) — #1437, model-agnosticism concern.
- [anchorwatch-dev/anchorwatch](https://github.com/anchorwatch-dev/anchorwatch) · [notdp/hive](https://github.com/notdp/hive) · [pleaseai/honmoon](https://github.com/pleaseai/honmoon) · [JoshuaOliphant/claude-plugins](https://github.com/JoshuaOliphant/claude-plugins) · [makikub/kb-notebooklm-podcast](https://github.com/makikub/kb-notebooklm-podcast) · [thkt/dotclaude](https://github.com/thkt/dotclaude) · [giadaf-boosha/claude-code](https://github.com/giadaf-boosha/claude-code) — timeline cross-referencers.
- [96loveslife/big_model_radar](https://github.com/96loveslife/big_model_radar) · [junlinzhao327-oss/big_model_radar](https://github.com/junlinzhao327-oss/big_model_radar) — one bot's daily digest; 7 of the 23 cross-references, low signal.
- [conorluddy/tokenblast.cc](https://github.com/conorluddy/tokenblast.cc) · [diegorv/claude-functions-hook](https://github.com/diegorv/claude-functions-hook) · [djnsty23/claude-auto-dev](https://github.com/djnsty23/claude-auto-dev) · [link-assistant/hive-mind](https://github.com/link-assistant/hive-mind) · [noopz/commonplace](https://github.com/noopz/commonplace) · [shcv/harness-investigations](https://github.com/shcv/harness-investigations) · [TheSmokeDev/taskchad-os](https://github.com/TheSmokeDev/taskchad-os) · [TransmuteLabs/Catalyst](https://github.com/TransmuteLabs/Catalyst) · [TransmuteLabs/Catalyst-CC-Patch](https://github.com/TransmuteLabs/Catalyst-CC-Patch) · [wandercom/kindex](https://github.com/wandercom/kindex) — code-index hits for `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — appeared in the same code index; this operator's own sibling repo.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; `kb_setup.recall_work`, the two 2026-09-10 research reports, and the guard stack.
