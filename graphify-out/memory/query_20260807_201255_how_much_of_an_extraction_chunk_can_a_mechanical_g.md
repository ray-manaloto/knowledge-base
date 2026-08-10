---
type: "query"
date: "2026-08-07T20:12:55.381204+00:00"
question: "How much of an extraction chunk can a mechanical gate actually check?"
contributor: "graphify"
outcome: "corrected"
correction: "A mechanical gate can only check CONTRADICTIONS THAT NEED NO SEMANTICS — a relation-vocabulary allowlist is not a quality gate. Two candidate checks were written, measured against the real corpus, and DELETED: a closed relation allowlist fired 1,936 times across 25 chunks on 308 verbs in ordinary use (conceptually_related_to 575, rationale_for 307), because the extraction prompt's verb list ends in an ellipsis and the vocabulary is OPEN; and a singleton-verb heuristic flagged 182 of those 308, so calling 59% of the vocabulary suspicious narrows nothing. What survives with 0 false positives over 25 chunks: self-edges, cycles in part_of/requires/depends_on, and a symmetric contrasts_with emitted both ways. SEMANTIC DIRECTION IS NOT CHECKABLE — `bun_requirement requires channels` is backwards and produces neither a cycle nor a self-edge, so roughly 25 of 63 review findings are invisible to ANY such gate. Do not let a green mechanical gate stand in for a semantic review."
---

# Q: How much of an extraction chunk can a mechanical gate actually check?

## Answer

Only contradictions that need no semantics. Two candidate checks were written, measured against the real corpus, and DELETED: a closed relation allowlist fired 1936 times across 25 chunks on 308 verbs in ordinary use (conceptually_related_to 575, rationale_for 307) because the extraction prompt verb list ends in an ellipsis and the vocabulary is open; and a singleton-verb heuristic flagged 182 of those 308, so calling 59 percent of the vocabulary suspicious narrows nothing. What survives with 0 false positives over 25 chunks: self-edges, cycles in part_of/requires/depends_on, and a symmetric contrasts_with emitted both ways. Semantic direction is NOT checkable - bun_requirement requires channels is backwards and produces no cycle and no self-edge, so roughly 25 of 63 review findings are invisible to any such gate.

## Outcome

- Signal: corrected
- Correction: A mechanical gate can only check CONTRADICTIONS THAT NEED NO SEMANTICS. A closed relation allowlist fired 1,936 times on an OPEN vocabulary and a singleton-verb heuristic flagged 59% of it, so both were deleted. What survives with 0 false positives: self-edges, cycles in part_of/requires/depends_on, symmetric contrasts_with. Semantic direction is NOT checkable — roughly 25 of 63 review findings are invisible to any such gate, so a green mechanical gate never stands in for a semantic review.