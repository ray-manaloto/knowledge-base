# Refutation lane: [circles] docs/secrets.md — 5 commits, "48 of 269 Bash calls (18%)"

## Verdict so far: REFUTED on two independent evidence defects (numbers + a named artifact that does not exist)

### D1 — "48 of 269 Bash calls (18%)" mixes two units. Real figure: 28 of 265 (10.6%).
Probe (scratchpad/count2.py over the round transcript
`/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/672f23a4-61dc-4e30-af59-21a860699ed6.jsonl`):

```
cut=2026-08-21T23:20:00Z totalBash= 265 calls_with_docs/secrets.md= 28 occurrences= 48 calls_with_'secrets.md'= 28
```

48 is the **occurrence** count (a command naming the path 3x counts 3). The finding
states it as a **call** count against a call denominator. The 18% headline is
~1.7x inflated; true per-call rate 10.6%.
CONTROL: the same script's per-call counter returns 14 for
`sources/media/dotfiles-secrets-guide.md` and 9 for `.claude/settings.json`, i.e. it
discriminates and is not stuck on one value.
NOT refuted by this: docs/secrets.md IS still the #1 repo path by per-call count (28).

### D2 — `dotfiles/docs/direction/` does not exist. The root-cause sentence names it as a thing "no one read".
```
cd ~/dev/github/ray-manaloto/dotfiles && find . -type d -name 'direction*' -not -path './.git/*'
  -> (no output, rc=0)
CONTROL: find . -type d -name 'specs'  -> ./docs/specs, ./docs/ultrapowers/specs, ...
CONTROL: find . -type d -name 'adr*'   -> ./docs/adr
```
`docs/direction/` is a **knowledge-base** path (CLAUDE.md layout table), not a dotfiles
path. The finding attributes it to dotfiles ("dotfiles' own docs/direction/").

### D3 — "a single 204-line document" is its size at BIRTH, not its size.
```
bc9d0b71 204 | 34a8aac7 212 | 0c142c68 217 | dbb7bdcd 242 | fbc80305 322 | HEAD 322
```
It is a 322-line document that grew +58%. And the diff shape of the last "correction"
(fbc80305: +88/-8) is overwhelmingly ADDITIVE, not corrective.

### D2 (hardened) — dotfiles tracks ZERO files matching "direction"
```
cd ~/dev/github/ray-manaloto/dotfiles && git ls-files | grep -i 'direction'   -> rc=1, no output
CONTROL git ls-files | grep -i 'secrets-takeover' -> docs/research/kb/reports/agents/adversarial-secrets-takeover-20260730.md
                                                    docs/specs/secrets-takeover.md
CONTROL git ls-files docs/adr                     -> docs/adr/0001-hk-hooks-do-not-run-in-ci.md, docs/adr/README.md
```
The "decision records" the finding gestures at are really
`docs/research/kb/decisions/secrets-cli-grilling-2026-08-04b.md`
(sources/media/dotfiles-secrets-decision.md frontmatter `source_path:`).
`docs/direction/` is a **knowledge-base** directory (5 files, `docs/direction/2026-08-1*-ray-directives.md`).

## What DOES hold (stated so the corrected finding can be re-filed)

| sub-claim | probe | verdict |
|---|---|---|
| 5 commits touch docs/secrets.md on main..repowise-mcp-0821 | `git log --oneline main..repowise-mcp-0821 -- docs/secrets.md \| wc -l` -> 5 | HOLDS |
| authored ~20:44 UTC | first Bash naming docs/secrets.md 2026-08-21T20:44:15Z; bc9d0b71 committed 15:46:47 CDT = 20:46:47Z | HOLDS |
| merged to graph BEFORE the takeover spec was read | merge f4b3a2d9 @ 16:37:39 CDT = **21:37:39Z**; first tool_use naming `secrets-takeover` = **21:46:26Z** (Agent) | HOLDS |
| first subagent report never covered the REPLACED decision | `grep -ni -e secrets-takeover -e REPLACED -e 'drop fnox' .agent/kb/reports/agents/dotfiles-fnox-secret-management.md` -> 0 relevant; CONTROL `grep -ci fnox` -> **134** | HOLDS |
| 11-line caveat added post-extraction | `git show --numstat 34a8aac7` -> `11 0` on each of the 3 vendored files | HOLDS |
| a completed 42-node chunk | nodes grouped by source_file in sources/extractions/dotfiles-secrets-docs.json -> guide 97, evidence 93, **rule 42** | HOLDS |
| second research subagent = call 0268 | Agent @ 21:46:26Z is all-tool index 269 (1-based) = 0268 (0-based) | HOLDS |
| U28 21:54:36 / U33 22:43:43 | transcript user turns at exactly 21:54:36Z ("yes make sure the graphify memory is correct…") and 22:43:43Z | HOLDS (numbering differs, timestamps exact) |
| docs/secrets.md is the most-touched path | broad path regex over 265 round Bash calls: #1 at 28 calls (next: guide.md 14, agent report 13, ~/.config/fnox/config.toml 11, .codex/config.toml 10) | HOLDS |

## Cross-finding contradiction
Finding 1 uses the same `269 Bash calls` denominator; the measured round total is
**265** (`cut=2026-08-21T23:20:00Z totalBash=265`; 274 only if you include the next
day's review calls). Finding 1's `73` is a *window* count (calls 0050..0305) while
finding 3's `48` is a *token-occurrence* count — two incompatible numerators sharing
one wrong denominator, neither labelled. `REPOWISE` itself appears in only **22** of
265 Bash calls (48 occurrences — coincidentally the same 48).
