---
type: "query"
date: "2026-08-07T20:12:55.381204+00:00"
question: "How much of an extraction chunk can a mechanical gate actually check?"
contributor: "graphify"
outcome: "corrected"
---

# Q: How much of an extraction chunk can a mechanical gate actually check?

## Answer

Only contradictions that need no semantics. Two candidate checks were written, measured against the real corpus, and DELETED: a closed relation allowlist fired 1936 times across 25 chunks on 308 verbs in ordinary use (conceptually_related_to 575, rationale_for 307) because the extraction prompt verb list ends in an ellipsis and the vocabulary is open; and a singleton-verb heuristic flagged 182 of those 308, so calling 59 percent of the vocabulary suspicious narrows nothing. What survives with 0 false positives over 25 chunks: self-edges, cycles in part_of/requires/depends_on, and a symmetric contrasts_with emitted both ways. Semantic direction is NOT checkable - bun_requirement requires channels is backwards and produces no cycle and no self-edge, so roughly 25 of 63 review findings are invisible to any such gate.

## Outcome

- Signal: corrected