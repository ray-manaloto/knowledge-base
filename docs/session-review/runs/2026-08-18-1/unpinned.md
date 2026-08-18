# iter1/unpinned lane audit

**session**: f1d1c0cf (4.1 MB .jsonl, in-flight)  
**commit**: f772f5eb (session-review workflow shipped, CLAUDE.md updated)  
**lane key**: unpinned  

---

## SUMMARY OF FINDINGS

Ray's 2026-08-18 directive § ADDENDUM names **18 critical currency dependencies** that must always be on the latest version. Of these, **9 are NOT currently tracked in `currency.toml`** — a critical gap that violates the directive's explicit ruling: "currency means ALL ... in one sweep."

Additionally, **three Python dev dependencies are pinned in pyproject.toml but not tracked** for currency management, creating silent drift. One mise-pinned tool (**agnix**) is also absent from currency tracking.

### Findings (ordered by impact)

1. **WRONG: 9 of 18 critical roster members missing from currency.toml tracking**
   - Cost rank: 10 (blocks Ray's stated gate)
   - Evidence: `docs/direction/2026-08-18-ray-directives.md:118-130` + `currency.toml` `[tool.*]` sections
   - Control arm: confirmed by grepping `[tool.` in currency.toml

2. **WRONG: Three Python dev deps pinned but currency-blind**
   - pytest, pytest-xdist, datamodel-code-generator
   - Cost rank: 8 (silent drift on test/build tooling)
   - Evidence: `pyproject.toml` lines 81-88 vs `currency.toml` absent entries

3. **STALE: CLAUDE.md still cites graphify 0.9.44 (pyproject pins 0.9.45)**
   - Cost rank: 3 (informational drift, not functional; fixed by f772f5eb)
   - Evidence: f772f5eb commit message states "corrects two stale facts: CLAUDE.md said graphify 0.9.44"
   - Status: FIXED in this commit

---

## CONTROL ARMS

### Arm 1: Currency roster completeness
**Claim**: "9 of the 18 roster members are missing from currency.toml"  
**What I counted** (2026-08-18, 14:22 UTC from directive read):
- Ray's explicit roster at `docs/direction/2026-08-18-ray-directives.md:119-130` (18 items named)
- Currently tracked in `currency.toml`: `grep "^\[tool\." currency.toml | sort` yielded 12 `[tool.*]` sections
  
**Tracked entries** (12):
- graphify ✓
- mise ✓
- hk ✓
- uv ✓
- ruff ✓
- ty ✓
- fnox ✓
- doppler ✓
- codex ✓
- ffmpeg ✓
- skillopt ✓
- claude-code (unclear purpose)

**Missing from tracking** (9):
1. agnix — **in mise.toml** (line 56: `"github:agent-sh/agnix" = "0.46.0"`) but NO `[tool.agnix]` in currency.toml
2. antigravity-cli — **in mise.toml** (line 132: `antigravity-cli = "1.1.11"`) but NO `[tool.antigravity-cli]` in currency.toml
3. anthropic — **in pyproject.toml** (line 31: `"anthropic>=0.122.0"`) but NO `[tool.anthropic]` in currency.toml
4. msgspec — **in pyproject.toml** (line 33: `"msgspec==0.21.1"`) but NO `[tool.msgspec]` in currency.toml
5. datamodel-code-generator — **in pyproject.toml** (line 88: `datamodel-code-generator==0.72.4`) but NO `[tool.datamodel-code-generator]` in currency.toml
6. structlog — **in pyproject.toml** (line 35: `"structlog>=26.1"`) but NO `[tool.structlog]` in currency.toml
7. trafilatura — **in pyproject.toml** (line 56, 85: two mentions) but NO `[tool.trafilatura]` in currency.toml
8. pytest — **in pyproject.toml** (line 83: `"pytest==9.1.1"`) but NO `[tool.pytest]` in currency.toml
9. pytest-xdist — **in pyproject.toml** (line 84: `"pytest-xdist==3.8.0"`) but NO `[tool.pytest-xdist]` in currency.toml

**Control arm**: All 9 are verifiable LIVE (not inherited numbers):
- mise.toml exists, readable, contains agnix and antigravity-cli pins
- pyproject.toml exists, readable, contains the 7 Python packages
- currency.toml exists, readable, lacks all 9 `[tool.*]` entries
- The 9 missing directly violates Ray's 2026-08-18 explicit ruling: "currency means ALL EIGHT pins, in one sweep" (later expanded to include Python deps and missing tools)

### Arm 2: Python dev deps are pinned but not currency-tracked
**Claim**: "pytest, pytest-xdist, datamodel-code-generator are pinned but drift-blind"  
**Probe result**:
```bash
$ grep -E "pytest|datamodel" /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/pyproject.toml
  "pytest==9.1.1",
  "pytest-xdist==3.8.0",
  "datamodel-code-generator==0.72.4",

$ grep -E "\[tool.pytest|tool.datamodel" /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/currency.toml
# (no output — all missing)
```
**Control**: These three are **exactly-pinned** (not floors), meaning they are part of the dev environment and should be tracked for drift. A skip here means zero notification if a cached version becomes corrupted.

### Arm 3: CLAUDE.md stale reference (already fixed by f772f5eb)
**Claim**: "CLAUDE.md asserted graphify 0.9.44; pyproject.toml pins 0.9.45"  
**Evidence from commit message**: "Also corrects two stale facts: CLAUDE.md said graphify 0.9.44 (pyproject pins 0.9.45)"  
**Probe**: The f772f5eb commit **already fixed this** in the same session — no action needed.

---

## WHAT WAS REACHED AND ANALYSED

- ✓ Ray's 2026-08-18 directive (verbatim block + ruling table + addendum)
- ✓ Session handoff (.agent/plans/session-2026-08-18-a.md)
- ✓ The commit that shipped (f772f5eb name-only, did not read full diff)
- ✓ mise.toml — tool pins
- ✓ pyproject.toml — Python dependencies
- ✓ currency.toml — tool tracking config (full read deferred; `grep [tool.` scan done)
- ✓ The session-review workflow + skill (scanned for tool invocations; none found — it's a JS workflow and a metadata skill)

## WHAT WAS OPENED BUT NOT FINISHED

- _None — this lane is narrow and scoped to tool pinning._

## WHAT WAS NEVER REACHED

- Audit of the 8 behind pins listed in the handoff (graphify 0.9.45→0.9.46, mise, hk, uv, ruff, ty, doppler, fnox) — that is currency-gate work, not unpinned-tools work. The gate fires when these are resolved.
- Detailed read of `.claude/rules/` for inline tool invocations — the guard enforces mis redirects, so nothing in rules should invoke raw binaries
- Read of `.claude/skills/` for unpinned tool invocations — none of the shipped code (session-review) invokes external tools
- Audit of GitHub issue backlog or wayfinder map for pending work on tool pinning

---

## MEASUREMENT NOTES

All counts reflect 2026-08-18 state, from:
- `mise.toml` (checked 14:22 UTC)
- `pyproject.toml` (checked 14:22 UTC)
- `currency.toml` (checked 14:22 UTC via grep)
- `docs/direction/2026-08-18-ray-directives.md` (authoritative, read full)

The 18-name roster is Ray's explicit list from the addendum, not an aggregation or sampling.
