# Corpus licensing & ToS: can we DISTRIBUTE a graph derived from 33 third-party sources?

**Status: COMPLETE** — (a)–(d) answered. Comparables research persisted verbatim at
`.agent/kb/reports/agents/research-comparable-projects-redistribution.md`.
**Date:** 2026-08-02
**Scope:** `sources/*.manifest` (**33**, not 32), `sources/media/` (47 files), `sources/extractions/` (17 chunks).
**This is not legal advice.** It maps which sources carry redistribution-hostile terms,
what the options are, and what a lawyer would need to look at.

---

## Headline — the premise of the question is wrong, and that is the finding

> "The repo currently ingests privately. It is becoming a distributable tool..."

**It is not private. `ray-manaloto/knowledge-base` is a PUBLIC GitHub repo with
`licenseInfo: null`.** Redistribution is not a future decision — it is the current
state, and it has been for the life of the repo.

And the split is exactly backwards from the question's assumption:

| Artifact | Tracked in git? | Risk |
|---|---|---|
| `graphify-out/graph.json`, `graph-prose.json`, `study-graph.json` | **NO — all gitignored** | the *safest* artifact (98% pointer index) |
| `sources/extractions/*.json` — 17 chunks, 2,817 nodes, **1,573 rationales**, 2.5 MB | **YES** | medium — derived paraphrase |
| `sources/media/` — 47 files, **1.1 MB of verbatim third-party prose** | **YES** | **highest — this is republication, not indexing** |
| `sources/*.manifest` — 33 url+SHA pointers | YES | none — pointers are facts |

**So the repo already publishes the two riskiest things and does not publish the
graph.** "Becoming a distributable tool" would *add* the graph — the artifact with the
strongest fair-use posture. The exposure that needs attention is the one that already
shipped.

### Public NOW vs staged-but-not-yet-pushed — the intervention window is open

I separated what is on `origin/main` (genuinely public) from what is only on the local
branch `feat/ingest-mattpocock-skills`:

| | On `origin/main` (public) | Local branch only |
|---|---|---|
| `sources/media/` | **18 files** | **+29 aihero.dev files** |
| `sources/extractions/` | 16 chunks | +1 chunk |

**The 29 verbatim aihero.dev articles are NOT public yet.** They landed locally today
(2026-08-02 15:12, commit `ed7619e`) and are not an ancestor of `origin/main`. The
single largest concentration of one commercial publisher's copyrighted prose is
staged and one `kb-land` away from publication. **This is the cheapest moment this
problem will ever have.**

Verified verbatim, not summarised: `sources/media/aihero-skills-grilling.md` is the
complete text of `https://www.aihero.dev/skills-grilling` — full headings and
paragraphs, carrying that site's own `title`/`slug`/`updatedAt` frontmatter.

What **is** already public and third-party (11 of the 18): Anthropic and Cerebras blog
posts and docs pages reproduced in full (`blog-*`, `ptc-doc.md`,
`claude-code-goal-docs.md`, `cerebras-knowledge-base.md`), two third-party posts
(`goal-engineering-ceccarelli.md`, `loop-engineering-sabrina.md`), **the X/Twitter
article retrieved through the auth wall**, and **two YouTube transcripts**. The other 7
are our own authored work and raise nothing.

### Second headline

The source everyone flagged is the one that is **already contained**. Three nobody
flagged are **in the aggregate graph**.

- `GitNexus` is **PolyForm Noncommercial 1.0.0** — confirmed on disk — but it is
  `scope = study`, and study sources are partitioned into `study-graph.json`,
  **never** the aggregate `graph.json`. Measured: `gitnexus` appears **0** times in
  `graph.json` and **218,754** times in `study-graph.json`.
- The three genuine redistribution problems in the **aggregate** graph are
  **basic-memory (AGPL-3.0)**, **awesome-claude-code (CC BY-NC-**ND**-4.0)**, and
  **system-prompts-leaks** (labelled CC0, but the repo does not own what it licenses).

---

## Method log (every probe with its control arm)

| # | Probe | Result | Control arm — did it discriminate? |
|---|---|---|---|
| 1 | `kb-query "license redistribution terms of service derivative work attribution" --prose --idf` | 886 nodes >0, **none about licensing**; top hit is `/usage` cost attribution | **Yes.** Arm A `"graphify extraction"` → 4 hits at 9.16 (`docs/how-it-works.md`). Arm B `"zqxjvbwkmpf"` → tool explicitly prints *"that is a real empty result, not a truncated one"*. Arm C `"copyright licence MIT Apache attribution notice"` → only **10** nodes >0, all incidental (a skill's own `license: Apache-2.0` frontmatter). **The corpus genuinely lacks licensing content.** |
| 2 | Licence read from the **on-disk clone at the pinned SHA** for all 33 sources | 33/33 have a LICENSE file; 0 unlicensed | **Yes.** `gh api repos/O/R/license` returned a correct SPDX id for **28** repos, so the 5 `NOASSERTION`s are real GitHub failures, not a dead probe. |
| 3 | Does `scope = study` stay out of the shipped graph? | Yes — `kb_setup/graph.py:564-582` partitions before merge | **Yes.** `gitnexus` in `graph.json` → **0**; in `study-graph.json` → **218,754**. Control `cognee` (corpus) in `graph.json` → **225,658**. Both directions fire. |
| 4 | Are the hostile sources in the aggregate? | basic-memory **167,161**; awesome-claude-code **1,781**; system-prompts-leaks **1,467** | Same probe as #3, already shown to discriminate (0 vs 225,658). |
| 5 | `curl https://www.aihero.dev/robots.txt` | `User-Agent: *` → `Allow: /`; only account/transactional paths disallowed. `GPTBot` explicitly `Allow: /`. The scraped `/skills-*` paths are **not** disallowed. | **Yes.** Control `claude.com/robots.txt` also returned a real policy. A 404/empty would have been distinguishable. |

**Probe #1 is corroborated by the tracker**: issue #23 lists *"Legal/ToS hygiene"* as
**searched but unverified** — "one data point only (Read the Docs asks: honor
ETag/Last-Modified, rate-limit)... No robots.txt RFC semantics, no vendor ToS text."
The graph's silence is an accurate reflection of a known gap, not a query failure.

---

## (a) Licence inventory — all 33 pinned sources

Read from `sources/<name>/LICENSE` in the **on-disk clone at the pinned commit**, not
from GitHub's licence field.

### Redistribution-hostile (4)

| Source | Licence (on disk) | GH field | scope | In shipped `graph.json`? | Problem |
|---|---|---|---|---|---|
| **awesome-claude-code** | **CC BY-NC-ND 4.0** | `NOASSERTION` | corpus | **YES — 1,781** | **NoDerivatives + NonCommercial.** The sharpest single conflict. |
| **basic-memory** | **AGPL-3.0** | `AGPL-3.0` | corpus | **YES — 167,161** | Strong copyleft + network clause. Largest footprint of any hostile source. |
| **system-prompts-leaks** | CC0-1.0 *(nominal)* | `CC0-1.0` | corpus | **YES — 1,467** | The repo **does not own** the prompts it CC0s. See below. |
| **GitNexus** | **PolyForm-Noncommercial-1.0.0** | `NOASSERTION` | **study** | **NO — 0** | Noncommercial only — but **already partitioned out**. |

### Permissive (29)

| Licence | Count | Sources |
|---|---|---|
| **MIT** | 18 | agents, antigravity-plugin-cc-chris, antigravity-plugin-cc-marcos, claude-code-memory-setup, code-review-graph *(study)*, codebase-memory-mcp *(study)*, codegraph, codex-orchestration, deer-flow, ecc, fable-advisor, fable-orchestrator, fable5-orchestrator, last30days-skill, learn-claude-code, mattpocock-skills, mindwalk *(study)*, OpenSymphony, Sol-Orchestrator, skillopt, agent-harness-docs |
| **Apache-2.0** | 6 | claude-plugins-community, cognee, cymphony, graphify *(+LICENSE-MIT dual)*, pensyve, stokowski, symphony |
| **CC0-1.0** | 1 | awesome-harness-engineering |

*(MIT row lists 21 names; 18 are `scope=corpus`, 3 are `study`.)*

**GitHub's licence field is unreliable here — 5 demonstrated failures**, all where the
on-disk LICENSE is unambiguous:

| Source | On disk | GitHub says |
|---|---|---|
| GitNexus | PolyForm-Noncommercial-1.0.0 | `NOASSERTION` |
| pensyve | Apache-2.0 | `NOASSERTION` |
| agent-harness-docs | MIT | `NOASSERTION` |
| awesome-claude-code | CC BY-NC-ND-4.0 | `NOASSERTION` |
| awesome-harness-engineering | CC0 | `NOASSERTION` |

The task brief said cognee also reports `NOASSERTION`; **it does not now** — `gh api`
returned `Apache-2.0`, matching disk. Either it was fixed upstream or the earlier
observation was of a different field. Flagging the discrepancy rather than silently
overwriting it.

### The three that actually matter

**1. `awesome-claude-code` — CC BY-NC-ND 4.0. The hardest stop.**
Verbatim from `sources/awesome-claude-code/LICENSE`:

> Awesome Claude Code © 2026 by hesreallyhim is licensed under Creative Commons
> Attribution-NonCommercial-**NoDerivatives** 4.0 International.
>
> If you are interested in making a project that utilizes this list **in a modified
> form, you are welcome to contact the maintainer.** This license was adopted to
> prevent appropriation of the labor of myself and the developers whose work is
> featured on this list from being used in harmful or predatory ways...

Two independent blockers, and **ND is the harder one**. NC can be satisfied by not
charging; **ND forbids distributing adapted material at all**. A knowledge graph of
concept nodes with generated rationales is close to a textbook "adaptation". CC's own
FAQ treats ND as barring distribution of a remix even for free.

**The good news is written into the licence**: the maintainer explicitly invites
contact for modified-form use. This is a *permission to ask*, not a permission — but
it is the cheapest fix available anywhere in this report, and the licence text names it.

**2. `basic-memory` — AGPL-3.0, and by far the biggest footprint (167,161 hits).**
The live question is whether a *knowledge graph describing the code* is a "modified
version" or "work based on" the program. For an AST-derived graph, the honest answer
is that it is closer to an index than to a port — but 167,161 occurrences is a lot of
extracted structure, and AGPL §13's network clause is designed to reach exactly the
"we serve it over a network" posture that `kb-serve` has. This is the one where a
lawyer's answer is genuinely load-bearing, not a formality.

**3. `system-prompts-leaks` — the CC0 label is not protective.**
The repo is `asgeirtj/system_prompts_leaks`, licensed CC0-1.0. Its content is
**leaked verbatim proprietary system prompts** from Anthropic, OpenAI, Google, xAI,
DeepSeek, Meta, Microsoft, Mistral, Notion, Perplexity, Qwen, Kimi, Cursor — its own
README says *"Leaked system prompts, captured verbatim"*. The tree includes
`Anthropic/Claude Code/bundled-skills/` (Anthropic's shipped skill sources) and
33 files under `OpenAI/`.

A CC0 dedication only waives rights the dedicator **holds**. asgeirtj holds no
copyright in Anthropic's or OpenAI's prompts, so the CC0 file is legally inert as to
that content. My inventory script labelled it `CC0` — **that label is wrong in
substance and I am flagging it rather than reporting it**. Distributing a graph
derived from it is a materially different act from ingesting it privately, and this
is the source most likely to attract a direct complaint from a named company, not
least because those companies are also this project's vendors.

(Mitigating, not exculpating: the README notes the Washington Post and CEPS built
public artifacts from the same repo, so it is widely mirrored and no takedown has
evidently landed. Widely-tolerated is not licensed.)

---

## (b) Is a derived knowledge graph a derivative work?

### First: what the artifact ACTUALLY contains (measured, not assumed)

This is the evidentiary core, and it is better than expected. I surveyed **every
field of all 140,680 nodes** in `graphify-out/graph.json`:

| Field | Nodes | % | What it is |
|---|---|---|---|
| `label`, `norm_label`, `community_name` | 140,680 | 100% | symbol / file / concept **name** |
| `source_file` | 140,680 | 100% | **path** |
| `source_location` | 139,304 | 99.0% | **line number** |
| `_origin: ast` | 137,863 | **98.0%** | pure structural index |
| `source_url` / `captured_at` / `author` / `contributor` | 2,817 | 2.0% | **per-node provenance, already built in** |
| `rationale` | 1,577 | 1.1% | newly-authored 1–3 sentence paraphrase |

**There is no `code`, `body`, `text`, `content`, `snippet`, `source_code`, or
`docstring` field anywhere in the graph.** The 98% AST majority stores *facts about*
the code — "symbol `X` is at path `Y` line `Z`" — and not one byte of the code itself.

**The one honest exception, precisely sized:** 742 `label` values exceed 200 chars
(203.6 KB total), of which exactly **3** are multi-line verbatim code — all JS import
destructuring blocks from test files. The single longest label (665 chars) is *our own*
goal text, not third-party content. So "the graph contains no verbatim third-party
source" is true to within 3 nodes out of 140,680, and I would state it that way rather
than absolutely.

This matters enormously, because it means:

- **For the 98% AST majority the graph is an index, not a copy.** File paths, symbol
  names and line numbers are facts. Under *Feist* facts are uncopyrightable; short
  names are outside copyright; and *Google v. Oracle* (2021) found even declaring code
  plus its structure to be fair use in a reimplementation. An index that lets you find
  where something lives, and cannot reconstruct it, is about as defensible as derived
  data gets. **This substantially defuses the AGPL/basic-memory concern** — 167,161
  `basic-memory` hits sounds alarming and is in fact 167,161 *pointers*.
- **The 1.1% with rationales is where the real exposure is** — that is newly-authored
  prose that paraphrases a specific source passage, and it is exactly the material
  drawn from `sources/media/` and the curated lists.

So the risk is **not** proportional to node count. It is concentrated in ~1.1% of the
graph, and that 1.1% is precisely the part that already carries `source_url` and
`captured_at`.

### Three legal frames, which do not agree

The graph is: concept nodes carrying a 1–3 sentence rationale, edges, and
`source_url` / `captured_at` provenance. Three distinct frames apply and
**they do not agree with each other** — which is itself the finding.

### US — copyright + fair use

- **Facts and ideas are not copyrightable** (*Feist*); **structure, selection and
  arrangement** can be. A graph of concepts extracted from a document is largely on
  the uncopyrightable side of that line — but the 1–3 sentence **rationales are newly
  authored text that paraphrases a specific source**, which is where the exposure sits.
- **Transformativeness** is the strongest argument: *Authors Guild v. Google* (2d Cir.
  2015) and *HathiTrust* upheld full-text ingestion for a **search index** as fair use,
  turning heavily on the fact that the *output* did not substitute for the original.
  A concept graph with pointers back to the source is close in shape to that.
- **The recent AI cases cut both ways and are not settled.** *Thomson Reuters v. Ross*
  (D. Del. 2025) rejected fair use where the intermediate output competed with the
  original. *Bartz v. Anthropic* and *Kadrey v. Meta* (N.D. Cal. 2025) found training
  transformative but were explicit that **acquisition/retention of the corpus is a
  separate question from the model**. That distinction maps directly onto our two
  artifacts: the **graph** is the defensible one; **`sources/media/` vendored verbatim
  prose is not the same act** and does not inherit the graph's argument.
- **The amount that matters is per-source substitution**, not corpus totals. A graph
  that lets a user skip reading `awesome-claude-code` is closer to substitution than
  one that routes them to it.

### EU/UK — the *sui generis* database right

This is the frame most likely to be overlooked and it does **not** care about fair use.

- Dir. 96/9/EC gives a **15-year right, separate from copyright**, to whoever made a
  substantial investment in obtaining/verifying/presenting a database. It is infringed
  by extraction/re-utilisation of a **substantial part**, *and* by repeated extraction
  of insubstantial parts.
- **`awesome-claude-code` is a paradigm protected database** — a curated list is
  precisely "selection and arrangement plus investment". Its NC-ND licence and its
  maintainer's stated rationale ("prevent appropriation of the labor") read as an
  explicit assertion of that interest.
- **There is no fair-use defence to database right.** The EU TDM exceptions (DSM Art.
  3 research / **Art. 4 commercial, which is opt-out-able**) are the relevant carve-outs,
  and a licence saying NoDerivatives is a plausible **Art. 4 reservation**.
- **UK post-Brexit**: the UK kept the database right but it is only available to
  UK/EEA makers; the UK's TDM exception is research-and-non-commercial only. A
  *distributed commercial* tool is squarely outside it.

### The practical synthesis

| Artifact | Share of graph | US fair use | EU database right | Verdict |
|---|---|---|---|---|
| AST nodes: path + symbol + line, no code body | **98.0%** | **strong** (facts/index; *Feist*, *Google v. Oracle*) | low | **ship** |
| Concept nodes + 1–3 sentence rationales from prose | **1.1%** | plausible-but-untested | **real risk where the source is a curated list** | **ship with opt-out + attribution** |
| `sources/media/` **verbatim vendored prose** (47 files, tracked in git) | n/a — separate tree | **weak; this is copying, not indexing** | **high** | **do not ship** |
| Anything derived from `system-prompts-leaks` | 1,467 hits | not the issue — upstream rights are third parties' | n/a | **drop** |

**The single most useful distinction in this whole report**: the *graph* and the
*vendored corpus* are different acts with different defences, and they are currently
in one repo. Almost every option below is a way of separating them. The graph is the
defensible artifact; `sources/media/` is the one that is plainly copying.

### Two compliance gaps that are cheap, mandatory, and currently unmet

Independent of any judgement call above, these are unambiguous:

1. **This repo has no licence of its own.** `git ls-files` matches no
   `LICENSE`/`NOTICE`/`COPYING` at any path, and `pyproject.toml` has no `license`
   field. Shipping an unlicensed tool means recipients receive **no rights at all** —
   a distribution problem entirely separate from the corpus, and the first thing any
   downstream consumer or lawyer will ask about.
2. **Apache-2.0 §4(d) NOTICE propagation is unmet.** Four pinned Apache sources ship a
   `NOTICE` file — **graphify, cymphony, stokowski, symphony** — and §4(d) requires
   derivative works to carry those notices. Nothing in this repo does.
   (cognee, claude-plugins-community and pensyve ship no NOTICE, so they impose no
   §4(d) obligation.) MIT's "include the copyright notice in all copies or substantial
   portions" is arguably not triggered by an index, but an attribution manifest
   satisfies all 24 MIT/Apache sources at once for near-zero cost.

Neither of these requires a legal opinion. Both should be fixed regardless of which
option below is chosen.

---

## (c) ToS for scraped prose — `sources/media/`

47 files. Provenance discipline is **already good**: 34 carry a YAML header with
`source_url`, and many add `captured_at`, `content_sha256`, `provenance: primary`, and
a `retrieval:` note. That is most of an attribution manifest already built.

### Domain concentration

| Domain | Files | Nature |
|---|---|---|
| `www.aihero.dev` | **29** | Matt Pocock's **commercial** course/newsletter site |
| `claude.com` | 3 | Anthropic |
| `x.com` | 1 | X/Twitter |
| `www.cerebras.ai` | 1 | Cerebras |

**29 of 34 provenanced files are one commercial publisher.** That concentration is the
ToS story: this is not a broad crawl, it is a near-complete mirror of one site's
skills content. Note `sources/mattpocock-skills.manifest` separately pins the **MIT**
`mattpocock/skills` repo — so the *code* is MIT-licensed and clean, while the *prose
articles about it* on aihero.dev are all-rights-reserved editorial content. **Those are
two different rights holders' worth of terms on one body of material**, and the MIT
repo does not launder the blog posts.

- **robots.txt permits the fetch** (verified above, with control) — `Allow: /` for `*`
  and for `GPTBot`; the scraped `/skills-*` paths are not disallowed.
- **But robots.txt governs crawling, not republication.** No robots directive grants
  redistribution rights, and aihero.dev publishes no separate content licence I found.
  Default is all-rights-reserved.

### Two sharper problems in the unprovenanced tail

13 files carry **no `source_url`**. They split cleanly:

- **Ours — no issue** (authored in-repo): `framework-plan-ladybug.md`,
  `autonomous-execution-program-20260719.md`, `second-brain-report-20260722b.md`,
  `claude-code-memory-plan.md`/`.pdf`, `harness-engineering-research.json`,
  `marketplace-235-relevant.txt`.
- **Third-party with provenance missing** — `ptc-doc.md` and `claude-code-goal-docs.md`
  (Anthropic docs), `goal-engineering-ceccarelli.md`, `loop-engineering-sabrina.md`
  (third-party posts), `yt-rtutpoT4SYg.txt`, `yt-9CiOwbmOKdU-memory.md` (YouTube
  transcripts).

Two of these are worse than the aihero set:

1. **YouTube transcripts.** YouTube's ToS specifically prohibits accessing/downloading
   content except through the interface or with written permission. A transcript is a
   verbatim reproduction of the creator's spoken words — copyrightable, and the
   creator (not YouTube) holds it. `CLAUDE.md` documents `kb-transcribe` (local
   faster-whisper) as a supported path, so this is a **designed-in** pipeline, not an
   accident. Redistributing transcripts is the clearest ToS breach in the media set.
2. **The X/Twitter article** — `x-towards-ai-graph-engineering.md` records
   `retrieval: "logged-in Chrome (graphify fetch hit the X auth wall)"`. That is a
   documented note that an access control was worked around by using an authenticated
   session. X's ToS prohibits scraping without prior consent. The honesty of the
   header is admirable and it is also, verbatim, the fact a plaintiff would quote.
   In the US this is where anti-circumvention/CFAA-adjacent arguments live (post-*Van
   Buren*/*hiQ* they are much weaker for public data, but this was **not** public data —
   it was behind auth).

---

## (d) What comparable projects do

Full verbatim report: **`.agent/kb/reports/agents/research-comparable-projects-redistribution.md`**.
Summary of what transfers:

| Project | Derived artifact's licence | Ships corpus or recipe? | Attribution | Gate / takedown |
|---|---|---|---|---|
| **DevDocs** | MPL-2.0 on the *scraper*; each source's own licence governs its content | **Both, separate tracks** — recipe in git, corpus to its own S3/CDN (`public/docs/**` gitignored) | **Mandatory `options[:attribution]` per scraper**, code-enforced via `AttributionFilter`, rendered in every page footer + a public table at `/about` | **Hard pre-inclusion gate**; no takedown process |
| tldr-pages | CC-BY-4.0 content / MIT tooling | corpus (hand-authored) | the blanket CC-BY + a CLA | n/a |
| Dash/Zeal | **no licence field at all** | recipe in git; corpus to Kapeli's CDN, then auto-deleted from git | `author` = submitter only | n/a |
| awesome-lists | **CC0 recommended** by `sindresorhus/awesome` | corpus | separate LICENSE file | prevention by convention |
| HuggingFace | single `license:` enum; **no multi-source schema exists** | corpus | prose per-source table | reactive **DMCA** only |
| Common Crawl | ToU: "respect third-party rights", as-is, **user indemnifies CC** | corpus | none | forward-only robots opt-out |
| The Pile | — | corpus | — | **quiet retroactive removal** (Books3, 2023) |
| nixpkgs / Homebrew / img2dataset | — | **recipe only** — URL + hash, user fetches | n/a | n/a by construction |
| Kubernetes | — | — | **`LICENSES/vendor/<org>/<repo>/LICENSE`** — every dependency's actual licence text mirrored at its own path, tool-generated | n/a |

**The four patterns the field has converged on:**

1. **Disclaim, don't verify.** Every large scraped corpus (Common Crawl, HF, C4/RedPajama,
   The Pile) pushes copyright responsibility downstream and enforces reactively via DMCA.
   **DevDocs is the sole exception** that reviews and gates at ingestion.
2. **Recipe vs corpus is load-bearing, and the strongest projects ship both on separate
   tracks** — small permissive code in git, generated artifact off-repo or not at all.
3. **Per-source, machine-readable attribution beats one blanket licence** once past a
   handful of sources (DevDocs' field; Kubernetes' licence mirror).
4. **A hard inclusion gate beats an after-the-fact takedown policy.** DevDocs is the only
   project here with a documented bar and a public paper trail of rejections; The Pile's
   Books3 history shows the cost of the reactive-only path.

### Three findings that directly change our plan

- **DevDocs' bar already decides our hardest case.** Its rule is that a source's licence
  *"must permit alteration, redistribution and commercial use"* — and it **rejected
  MongoDB (#397) specifically for a CC-BY-NC-SA NC clause**. `awesome-claude-code` is
  CC-BY-NC-**ND** — strictly worse (NC *and* ND). The closest analogue project, facing a
  weaker version of our exact problem, said no. That is strong precedent for excluding it.
- **Kubernetes' `LICENSES/<source>/LICENSE` mirror is better than my "NOTICE.md" option.**
  Apache §4(d) only obligates preserving an upstream NOTICE's *own* contents; **MIT has no
  NOTICE concept at all** — its condition is preserving *that project's own licence text*.
  A single hand-written NOTICE satisfies neither cleanly. A generated per-source mirror,
  verbatim-copied from each pinned commit at `kb-build` time, satisfies both — and my
  inventory script already reads exactly those files.
- **We already have the recipe/corpus split right**, and better than most: manifests are
  pinned url+SHA, and `graph.json` is gitignored. The gap is not architecture — it is
  (a) a mandatory per-source licence field that **gates** ingestion, and (b) the licence
  mirror. Both are precedented and cheap. Inventing a machine-readable multi-licence
  schema, by contrast, is genuinely novel work — **nobody in this survey has one**.

---

## Options

Five, ordered cheapest-first. They are **not exclusive** — the recommendation combines
1, 2, 4 and part of 3.

### 1. Licence mirror + `license` field + a repo licence (mandatory floor, ~1 day)

Three mechanical pieces, all precedented:

- **A generated `LICENSES/<source>/LICENSE` mirror** — the **Kubernetes** pattern —
  verbatim-copying each source's actual licence text from its pinned commit at
  `kb-build` time. This satisfies MIT's "preserve that project's own licence text"
  condition *and* Apache §4(d) NOTICE propagation, which a single hand-written
  `NOTICE.md` does not do cleanly for either.
- **A required `license =` field in `sources/*.manifest`** — the **DevDocs** pattern
  (`options[:attribution]`), plus the same on the media/extraction provenance schema,
  which today has `source_url`/`captured_at`/`author` but **no licence field — only 1
  of 47 media files records anything licence-like**.
- **A `LICENSE` for this repo**, which is currently public and unlicensed.

- **Pro:** discharges MIT ×18 and Apache-2.0 ×7 at near-zero cost; mechanically
  generable from data already on disk (my inventory script is ~90% of it); reviewable
  in a diff; fixes the unlicensed-repo defect; and makes option 2's gate *possible*,
  since you cannot gate on a field that does not exist.
- **Con:** does **nothing** for the four hostile sources. Attribution is not permission
  — NC/ND/AGPL are not attribution licences, and no mirror cures them.

### 2. Inclusion gate + exclusion list, enforced at build (~1–2 days)

Adopt **DevDocs' bar** — *a source's licence must permit alteration, redistribution and
commercial use* — as a check over the `license` field from option 1, and extend the
manifest with `redistribute = false` (or reuse `scope = study`, which **already provably
works** — measured 0 vs 218,754). Excluded sources stay ingestible locally but are
partitioned out of any shipped artifact.

- **Pro:** the partition mechanism **already exists and is proven in the built
  artifact** — this is configuration plus a gate, not new architecture. The bar is not
  invented: it is the closest analogue project's stated rule, with public rejection
  precedent (MongoDB for an NC clause). Applied here it cleanly removes
  awesome-claude-code (NC+ND) and system-prompts-leaks, and forces an explicit decision
  on basic-memory rather than a drift.
- **Con:** you lose those sources from the *distributed* corpus. Someone must keep the
  field accurate — which is why it should be a `mise run lint` gate, not a convention.
  Per `probes-need-a-control-arm.md`, prove the FAIL direction: add a fixture source
  with an NC licence and confirm the gate rejects it.

### 3. Ship the engine, not the corpus — rebuild-on-install

Ship `kb_setup` + the 33 manifests + the extraction chunks; the **user** runs
`kb-build`, which clones from upstream at the pinned SHA on their machine. Each user
obtains each source directly from its rights holder under its own licence.

- **Pro:** the strongest position by a wide margin. You distribute *pointers and a
  method* — facts and your own code — and never a copy. It also matches what the repo
  **already does** for `sources/<name>/` clones and for `graph.json` (both gitignored,
  rebuilt). This is not a new idea here; it is the existing invariant extended.
- **Con:** does not save the **extraction chunks** — those carry 1,573 authored
  rationales derived from prose and are tracked. And it does not save
  `sources/media/`, whose whole purpose is that the content is *not* re-fetchable.
  A first-run build is slow and network-dependent.

### 4. Purge / de-vendor `sources/media/`

Replace verbatim prose with a fetch manifest (URL + `content_sha256` + `captured_at`,
all of which are **already recorded**) so the user re-fetches. Keep verbatim only where
a licence permits it.

- **Pro:** removes the single clearest act of republication. The `content_sha256`
  already present makes re-fetch verifiable.
- **Con:** breaks Invariant 3 (reproducibility) for anything that later 404s — which is
  precisely why media was vendored. YouTube transcripts genuinely cannot be re-derived
  without re-downloading. This trades legal risk for reproducibility risk, and that
  trade should be made deliberately.

### 5. Ask (only real for one source, and it is invited)

`awesome-claude-code`'s LICENSE says in terms: *"If you are interested in making a
project that utilizes this list in a modified form, you are welcome to contact the
maintainer."*

- **Pro:** the licence names the path. One email plausibly converts the hardest
  blocker in the set into a written permission.
- **Con:** it is a request, and the answer may be no. Not scalable past one or two
  sources.

---

## Recommendation

**Do 1 + 2 + 4 now; adopt 3 as the standing posture; send the email in 5. Do not
merge `feat/ingest-mattpocock-skills` as it stands.**

Concretely, in priority order:

1. **Hold the branch.** The 29 verbatim aihero.dev articles are not yet public. Convert
   that chunk to fetch-manifests (option 4) *before* `kb-land`, or land it with the
   media files dropped and only the extraction chunk kept. This is the one decision
   with a closing window, and it costs almost nothing today.
2. **Add a `LICENSE` to this repo** and a generated `NOTICE.md`. The repo is public and
   unlicensed right now; that is a defect independent of everything else here.
3. **Set `redistribute = false` (or `scope = study`) on `system-prompts-leaks`** and
   drop it from the shipped graph. This is the one source where the licence on the tin
   does not describe the rights, the affected parties are large and identifiable, and
   they are also this project's vendors. Low corpus value (1,467 hits), high
   asymmetric risk.
4. **Exclude `awesome-claude-code` pending permission.** ND is a genuine bar to
   distributing an adaptation, 1,781 hits is not worth it, and **DevDocs rejected a
   strictly weaker case (MongoDB, NC-only)**. Send the email the licence invites; re-include
   if the maintainer agrees.
5. **Add the `license` field + the `LICENSES/<source>/` mirror + the DevDocs bar as a
   lint gate.** Cheap now, painful at 100 sources — and the gate is what stops this
   report from having to be written again.
6. **Get a lawyer's read on `basic-memory` (AGPL-3.0) specifically** — see below.
7. **Add a Common-Crawl-style disclaimer + a forward-only removal process.** That is the
   field's accepted floor, and we currently have neither. It is also the honest posture
   given items 1–7 in "could not determine".

**Leave `basic-memory` in for now, but flag it.** My measurement substantially defuses
it: 167,161 hits are 167,161 *pointers* (path + symbol + line, zero code body), which
is an index rather than a "work based on the Program". But AGPL §13's network clause is
designed for exactly the `kb-serve` posture, and I am not confident enough to call it
either way. This is the one item where a lawyer's answer changes the decision rather
than confirming it.

### What a lawyer actually needs to look at

Give them four things, not the whole repo:

1. **The node schema and the measurement above** — that 98% of nodes are
   path+symbol+line with no code body, and that verbatim third-party content is 3 nodes
   out of 140,680. Most of the analysis turns on this single fact.
2. **AGPL-3.0 §0 ("modify"/"based on") and §13 vs an AST index served over MCP** —
   the `basic-memory` question.
3. **CC BY-NC-ND 4.0 §2(a)(1)(B) "Adapted Material"** against a node carrying a
   1–3 sentence generated rationale — the `awesome-claude-code` question, and the
   general question for all prose-derived nodes.
4. **The `sources/media/` republication question**, which is ordinary copyright, not an
   AI question at all — plus the two ToS-specific items (YouTube's download prohibition;
   the X article whose own header records retrieval through an auth wall).

Ask them explicitly to answer for **both** US and EU/UK, because the frames diverge:
the *sui generis* database right has **no fair-use defence**, and `awesome-claude-code`
is a textbook protected database whose licence plausibly operates as a DSM Art. 4 TDM
opt-out.

---

## What I could NOT determine

Stated plainly, because each of these is a real gap and not a rhetorical hedge:

1. **Whether the rationales are legally "adaptations".** This is the central question
   for the prose 1.1% and it is genuinely unsettled. A 1–3 sentence abstractive summary
   with a pointer back is *shaped* like the transformative index upheld in
   *Authors Guild v. Google*, but no court has ruled on LLM-generated concept
   extraction. Anyone who tells you this is settled in either direction is wrong.
2. **Whether AGPL §13 is triggered by `kb-serve`.** Needs a lawyer. See above.
3. **aihero.dev's Terms of Service.** I verified `robots.txt` (permissive, with a
   control arm) but did **not** locate or read a ToS/content-licence page. Absent one,
   the default is all-rights-reserved — but I did not confirm there is no *more*
   permissive term, and 29 files hang on it.
4. **Whether any upstream source has already objected.** I found no takedown, but I did
   not search issue trackers or contact anyone. Absence of a complaint is not consent.
5. **The `cognee` `NOASSERTION` claim in the brief does not reproduce.** `gh api` returns
   `Apache-2.0` on both the `/license` and `/repos` endpoints today, matching disk.
   Control: GitNexus returns `NOASSERTION` on both, so the probe discriminates. Either
   it was fixed upstream or the original observation read a different field. **I did not
   determine which**, and I have not silently overwritten the brief's claim.
6. **Downstream/user-side liability if we ship a rebuild-on-install tool.** Option 3
   moves the copying to the user's machine. Whether that also moves the *liability*, or
   merely adds contributory-infringement exposure for us, is a real question I am not
   equipped to answer.
7. ~~The provenance of `system-prompts-leaks` per-file.~~ **Resolved on a second probe,
   and it partly exonerates the source.** The repo distinguishes them itself: its
   `Anthropic/Official/` directory (**34 files**) holds prompts *Anthropic published*
   at release, which the README labels *"Official published prompts, research artifacts
   & older versions"* and links separately from the extracted ones (e.g.
   `Anthropic/claude-fable-5.md` vs `Anthropic/Official/2026-06-09-claude-fable-5.md`).
   So the repo is **not** uniformly leaked material. This does not make the officially
   published prompts *licensed* for redistribution — publication is not a licence, and
   they remain Anthropic's copyright — but it means a per-directory exclusion could
   retain the official subset while dropping the leaks. **What I still could not
   determine** is the same split for the other 12 vendors (OpenAI, Google, xAI, …),
   which I did not audit.

## GitHub repos touched

**Read directly (LICENSE at the pinned SHA in `sources/<name>/`), all 33 pinned sources:**

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; issue #23, visibility/licence status, git history of `sources/media/`
- [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus) — **PolyForm Noncommercial 1.0.0**; the flagged source, confirmed contained in `study-graph.json`
- [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) — **CC BY-NC-ND 4.0**; the hardest blocker, and its maintainer-contact clause
- [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) — **AGPL-3.0**; largest hostile footprint (167,161 nodes)
- [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) — CC0 label over third-party prompts; `Anthropic/Official/` vs leaked split
- [ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) — CC0; the permissive awesome-list control case
- [topoteretes/cognee](https://github.com/topoteretes/cognee) — Apache-2.0 on disk **and** on both `gh api` routes; the brief's `NOASSERTION` claim did not reproduce
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — Apache-2.0 + `LICENSE-MIT`; **ships a NOTICE** (§4(d) obligation)
- [zaalipro/cymphony](https://github.com/zaalipro/cymphony), [Sugar-Coffee/stokowski](https://github.com/Sugar-Coffee/stokowski), [openai/symphony](https://github.com/openai/symphony) — Apache-2.0, each **ships a NOTICE** (§4(d) obligation)
- [major7apps/pensyve](https://github.com/major7apps/pensyve), [mrkhachaturov/agent-harness-docs](https://github.com/mrkhachaturov/agent-harness-docs) — licence correct on disk, `NOASSERTION` from GitHub (field-unreliability evidence)
- [anthropics/claude-plugins-community](https://github.com/anthropics/claude-plugins-community) — Apache-2.0, no NOTICE
- [mattpocock/skills](https://github.com/mattpocock/skills) — MIT; the code is clean while the aihero.dev articles about it are not
- MIT, permissive, no issue found: [wshobson/agents](https://github.com/wshobson/agents), [simplybychris/antigravity-plugin-cc](https://github.com/simplybychris/antigravity-plugin-cc), [MarcosNahuel/antigravity-plugin-cc](https://github.com/MarcosNahuel/antigravity-plugin-cc), [lucasrosati/claude-code-memory-setup](https://github.com/lucasrosati/claude-code-memory-setup), [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph), [deusdata/codebase-memory-mcp](https://github.com/deusdata/codebase-memory-mcp), [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph), [Cjbuilds/Codex-Orchestration](https://github.com/Cjbuilds/Codex-Orchestration), [bytedance/deer-flow](https://github.com/bytedance/deer-flow), [affaan-m/ECC](https://github.com/affaan-m/ECC), [DannyMac180/fable-advisor](https://github.com/DannyMac180/fable-advisor), [mar3co/fable-orchestrator](https://github.com/mar3co/fable-orchestrator), [Rylaa/fable5-orchestrator](https://github.com/Rylaa/fable5-orchestrator), [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill), [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code), [cosmtrek/mindwalk](https://github.com/cosmtrek/mindwalk), [kumanday/OpenSymphony](https://github.com/kumanday/OpenSymphony), [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt), [ReyJ94/Sol-Orchestrator](https://github.com/ReyJ94/Sol-Orchestrator)

**Comparables (via the delegated sub-agent — full enumeration in
`research-comparable-projects-redistribution.md`):**

- [freeCodeCamp/devdocs](https://github.com/freeCodeCamp/devdocs) — the closest analogue; per-source attribution field + hard inclusion gate + recipe/corpus split
- [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes) — `LICENSES/vendor/**` per-dependency licence-mirror, the pattern recommended above
- [tldr-pages/tldr](https://github.com/tldr-pages/tldr), [Kapeli/Dash-User-Contributions](https://github.com/Kapeli/Dash-User-Contributions), [sindresorhus/awesome](https://github.com/sindresorhus/awesome), [sindresorhus/awesome-lint](https://github.com/sindresorhus/awesome-lint) — attribution/licence conventions
- [EleutherAI/the-pile](https://github.com/EleutherAI/the-pile), [togethercomputer/RedPajama-Data](https://github.com/togethercomputer/RedPajama-Data), [huggingface/hub-docs](https://github.com/huggingface/hub-docs), [huggingface/datasets](https://github.com/huggingface/datasets) — takedown history and per-source licence conventions for scraped corpora
- [NixOS/nixpkgs](https://github.com/NixOS/nixpkgs), [Homebrew/homebrew-core](https://github.com/Homebrew/homebrew-core), [rom1504/img2dataset](https://github.com/rom1504/img2dataset) — ship-the-recipe precedents

**Non-GitHub sources consulted:** `aihero.dev/robots.txt` and `claude.com/robots.txt`
(fetched with control arm); the Common Crawl ToU, HuggingFace dataset-card/DMCA docs and
`apache.org/licenses/LICENSE-2.0` §4(d) via the sub-agent.
