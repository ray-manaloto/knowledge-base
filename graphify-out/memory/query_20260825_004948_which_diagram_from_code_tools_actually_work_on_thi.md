---
type: "query"
date: "2026-08-25T00:49:48.277247+00:00"
question: "Which diagram-from-code tools actually work on this repo, and what did the rejected ones actually fail on?"
contributor: "graphify"
outcome: "useful"
---

# Q: Which diagram-from-code tools actually work on this repo, and what did the rejected ones actually fail on?

## Answer

DIAGRAM-FROM-CODE TOOLING: ~30 CANDIDATES SURVEYED, 3 PROTOTYPED, 2 ROOT-CAUSED.
Measured 2026-08-24. Reports: `.agent/kb/reports/agents/2026-08-24-{annotation-candidates,annotation-sweep,diagram-gen}/`,
prototypes at `/tmp/diagram-proto/`, forensics at `/tmp/tool-forensics/`.

**THE HEADLINE, confirmed by two independent lanes: NO tool draws the four layers
Ray wants** (`SKILL.md` fence -> mise task -> python function -> config read). Every
candidate is Python-only; the markdown->TOML and TOML->python hops are THIS REPO'S
CONVENTIONS, and no external tool can discover a convention.

**`pushed_at` IS NOT THE LAST COMMIT DATE** — it moves on any branch/tag push,
including bots. pydoctrace reads "pushed today"; its last DEFAULT-BRANCH commit is
2026-04-14 and every 2026 commit is `[pre-commit.ci] autoupdate`. Its last RELEASE is
2024-02-27 — 2.5 years. code2flow's `pushed_at` is 2.5 years newer than any commit.
Two lucsorel repos shared a `pushed_at` to within 5 SECONDS — one batch event, not two
commits. **Use `/commits` on the default branch, and cross-check the release artifact.**

**THREE SHAPES PROTOTYPED end-to-end, artifacts comparable:**
- code2flow — static, 1.88s, 109 edges. rc=0, 1313 nodes/1978 edges over kb_setup.
  51 call sites unresolved, mostly this repo's deliberate function-local lazy imports,
  which defeat its static resolver. No ordering, so flowchart not sequence. Dormant
  since 2023-01-08, but consumed as one-shot JSON rather than a carried dependency.
- mermaid-trace — decorators -> real Mermaid SEQUENCE diagram, 0.10s. NEEDS THE CODE
  TO RUN, so it diagrams exercised paths only. Auto-names the callee participant after
  the first arg's TYPE (`PosixPath`) unless that arg is `self`.
- graphify's own graph — 7.54s, 139 edges, but DISQUALIFIED: see the 43% gap below.

**ANNOTATION BURDEN IS FAR SMALLER THAN 1,307 FUNCTIONS.** A trace decorator marks
ENTRY POINTS. `cli.py` has 59 `cmd ==` arms, so the real cost is <=59 decorators, one
per command — in practice one per pipeline you want drawn.

**`@sequenceDiagram` — REJECTED WRONGLY, then reversed.** `brijeshkulkarni/sequenceDiagram`,
PyPI `sequenceDiagram==0.0.3`. It is **the only candidate that emits Mermaid natively
from decorators**, and its blocker is TWO LINES: `listre.append(a)` at source lines 67
and 72 append the RAW int/float/bool, while line 42 does `", ".join(...)` which requires
strings. The object branch at line 74 DOES call `str()` — the asymmetry is visible in the
source. Any decorated call with a number or bool crashes; the README only escapes it by
using zero-argument functions. Patched at runtime it produced a real multi-participant
Mermaid diagram from a live `kb_setup` entry point. Two further defects: `resetseq()` is
dead code (reassigns a local, no `global`, so traces accumulate forever), and kwargs are
discarded — `greet(name="ray")` renders as `greet(tuple)`.

**`py2puml` — DISCARD, and not for the reason first assumed.** Not one bad file; THREE
independent failure classes: (1) `result.py:122` is `class Ok[T]:` — PEP 695 native
generics its resolver cannot see; (2) **29 of 95 files** use `if TYPE_CHECKING:` guarded
imports (the standard circular-import-avoidance pattern) and 26 need PERMANENTLY
un-guarding — trading a real correctness property for a diagram; (3) `generated/source_groups.py`
carries 10 PEP 695 `type` aliases and is MACHINE-REGENERATED, so any fix dies at the next
codegen. It builds the whole cross-module graph before emitting a line, so ANY ONE of 95
files zeroes out the entire run.

**"IT CRASHED" IS NOT A DIAGNOSIS.** Both verdicts above changed once someone read the
traceback. Ray's push-back on this was correct and is the durable lesson.


## Outcome

- Signal: useful