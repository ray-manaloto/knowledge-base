# Research Repo Enumeration: List Every Touched Repo

Every research artifact produced by an agent — deep reviews, spec
deltas, doc lookups, dependency audits — MUST end with a `## GitHub
repos touched` section listing every owner/repo URL whose source or
docs were consulted while producing the artifact.

## Why

Research artifacts accumulate over time. Without an enumeration section,
it becomes impossible to answer "which repos have we already researched?"
or "which repos does this finding depend on?" without re-reading every
artifact. The enumeration section is the cheap-to-grep index that makes
artifacts bisectable after the fact.

**In this repo it does one more job: it is the source backlog.** A repo an
agent read while researching is, by definition, a candidate corpus source.
Any repo enumerated in an artifact should either already have a
`sources/<name>.manifest`, or be appended to `sources/REGISTRY.md` — the
durable source backlog — in the same commit. That closes the loop between
"we read it once" and "the graph knows it".

## Format

At the bottom of every research artifact:

```markdown
## GitHub repos touched

- [owner/repo](https://github.com/owner/repo) — one-line reason
- [owner/repo](https://github.com/owner/repo) — one-line reason
```

Rules:

- Every repo whose source files, README, issues, or docs were read.
- Every repo whose documentation site was queried (via `llms.txt`, `.md`,
  or `mcp2cli`).
- One-line reason per entry — just enough to grep for later.
- Empty section is allowed (`## GitHub repos touched\n\n_None._`) if the
  artifact truly touches zero repos (rare).

## Applies to

- `.omc/kb/reports/**/*.md` — persisted agent reports.
- `.omc/research/**/*.md` — agent working research.
- Any other markdown artifact produced by a research workflow (deep
  review, spec delta, dependency audit, etc.).

## Not applies to

- Plans (`.omc/plans/**`) — plans describe intended work, not research
  findings.
- Session handoffs (`.omc/plans/session-*.md`) — the repos touched are
  implied by the commits in the session.
- Rule files, skill files, CLAUDE.md.
- Ingested corpus content under `sources/` — a source's provenance is its
  manifest (url + pinned SHA), which is stronger than an enumeration list.

## Enforcement

Documented, not machine-enforced: `.omc/**` is gitignored, so an hk check on
staged artifacts would be a no-op. This rule relies on reviewer enforcement
and on `agent-report-persistence.md`, which requires the artifact to exist on
disk in the first place.

## See also

- `research-doc-sources.md` — the sibling preference chain for fetching
  doc content.
- `agent-report-persistence.md` — enumeration is the final step before
  persisting a finding.
- `sources/REGISTRY.md` — the durable source backlog this rule feeds.
