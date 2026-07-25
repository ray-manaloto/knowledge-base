# Research Existing Tools/Services Before Building Custom

**Before writing ANY custom code, script, or config to accomplish a capability,
you MUST first research whether an existing tool, service, native feature, or
canonical pattern already provides it — and prefer that.** A CLI may already
ship the command (`graphify`, `gh`, `mise`, `uv`), a platform may already have
the feature (GitHub auto-merge / merge queue / `workflow_run`), an established
library may already solve it, or the tool's docs may show a canonical pattern.
Homegrown code is the LAST resort, not the first reach.

This is a **standing rule**. If you find yourself about to write a loop, a
poller, a parser, a detector, or a wrapper, STOP and research first.

## The hard gate (do this before writing custom code)

1. **Name the capability** you need in one sentence ("wait for CI to finish then
   merge", "split a document into chunks", "detect which backend graphify will
   pick").
2. **Research existing solutions FIRST** — walk `research-doc-sources.md`
   (starting at step 0: query this repo's own graph). Read the relevant CLI's
   `--help` and manual, the platform's feature docs + changelog, extensions,
   and libraries. Assume the native mechanism exists until you've confirmed it
   doesn't.
3. **Prefer the existing mechanism.** Custom code is justified ONLY when no
   existing tool/service fits, AND you record *why* in the code comment or PR
   body (which options you evaluated and why each was insufficient). Without
   that written justification, the default answer is "delete the custom code,
   use the existing tool."
4. **A known-flaky native tool is not license to hand-roll a replacement** —
   first check for a newer version, the documented robust usage, an extension,
   or an adjacent native feature that sidesteps the flaw.

### Worked failure

Asked to fix a ship/land CI-wait that used a fixed timeout, an agent hand-rolled
a custom polling loop — WITHOUT first researching that GitHub offers **native
auto-merge** (`gh pr merge --auto`), **merge queue**, `gh run watch`,
`workflow_run` triggers, and webhooks, several of which eliminate the polling
entirely. The maintainer had to send the agent back to research.

## graphify is where this rule earns its keep here

This repo's entire job is driving one tool. The temptation to reimplement a
piece of it is constant, and every time it has been checked, graphify already
had the feature:

- **Chunk merging** — `graphify merge-graphs` and the bundled merge driver
  exist; `kb_setup.graphify_ops.merge_chunk` is a *seam over them*, not a
  reimplementation.
- **Scale-out query** — native `push_to_neo4j()` / `push_to_falkordb()`
  exporters plus `--push <uri>`. The graph DB is the scale surface; do not
  invent a query layer, and do not put a 119MB `graph.json` in git.
- **Incremental re-extraction** — `graphify update` is AST-only and free. Do
  not write a differ.
- **Clustering + labelling** — `graphify cluster` / `label`, deterministic hub
  labels with no LLM. Do not write a labeller.

**Verify against the INSTALLED source, not the issue tracker.** graphify's
issues stay open after fixes ship — one nearly cost this repo a viable path
(issue #959 read as "custom OpenAI endpoints are blocked"; the feature had
shipped in 0.8.40). See `probes-need-a-control-arm.md`.

## Tool built-in facts (the original case)

Before designing custom detection logic, custom data variables, custom env-var
parsing, or custom helper scripts to discriminate environments / machines /
states, **research the tool's official docs first** and prefer its built-in
facts and canonical patterns over a homegrown solution.

The canonical example: a repo carried ~20 lines of custom container-detection
(`REMOTE_CONTAINERS` / `CODESPACES` / `DEVCONTAINER` env sniffing) feeding a
custom data variable — when the tool's own docs showed the pattern was a
one-line built-in runtime fact that is always correct and never depends on env
vars or stale config. The reinvention introduced a real bug.

Built-ins to check first: `mise` (`os`, `arch`, `config_root`, `{{env.…}}`),
`uv` (`--project`, dependency groups, optional-dependency extras), `gh`
(`--json` + `--jq`, `--watch`, auto-merge), `hk` (`Builtins.*`, `exclusive`,
`glob`), GitHub Actions (`runner.os`, `github.event_name`).

## Rules

1. **Before writing custom detection logic**, fetch the tool's official docs on
   the relevant feature. Look for built-in facts, canonical patterns, and
   "common gotchas" sections.
2. **Before introducing a custom data variable**, check whether a built-in fact
   already discriminates the cases you care about.
3. **Before writing a hook or postinstall step**, check whether the tool has a
   declarative way to express the same intent.
4. **Verify *which* native mechanism empirically.** A tool often exposes several
   near-synonyms; probe the real behaviour before committing — the
   documented-sounding one is not always the one that meets the requirement.
5. **Justify any custom solution in writing.** If you do introduce custom logic,
   the commit body or a rule file must say *why* the built-in approach is
   insufficient. Without that justification, the default answer is "delete the
   custom logic, use the built-in".

## Applies to

All tools used in this repo: graphify, mise, hk, uv/ruff/ty, pkl, taplo, rumdl,
gitleaks, agnix, gh, and any future additions. Reinvention is the most common
source of subtle bugs.

## See also

- `tool-currency-and-native-first.md` — the over-time sibling: the built-in you
  needed may have shipped since you last looked, and the custom code you wrote
  may now be dead weight.
- `zero-bash-logic.md` — when custom code IS justified, it is python, not bash.
- `research-doc-sources.md` — the doc-fetch chain this rule's research step walks.
