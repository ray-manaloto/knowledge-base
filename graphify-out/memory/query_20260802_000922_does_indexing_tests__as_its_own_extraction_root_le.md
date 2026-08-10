---
type: "query"
date: "2026-08-02T00:09:22.973750+00:00"
question: "Does indexing tests/ as its own extraction root let graphify affected answer 'which tests cover this symbol'?"
contributor: "graphify"
outcome: "corrected"
correction: "The first diagnosis — that graphify affected cannot link tests to the symbols they cover — was wrong. affected DOES link tests (affected '_state' reaches 9 test functions; a conftest fixture reaches 17 across two modules). The real cause is OURS: _SELF_TREES runs graphify extract TWICE and merge-graphs re-namespaces node ids per merge, leaving disjoint namespaces (knowledge-base::python:: vs tests::) that no edge can span — 3,368 tests-touching edges, 0 crossing, control 2,194 within python/. Decisive arm: cognee, extracted in ONE run, carries 10,099 test<->src edges in the same graph file. A config gap of ours, not a tool gap. Filed as #101; the combined-extraction fix is UNVERIFIED."
---

# Q: Does indexing tests/ as its own extraction root let graphify affected answer 'which tests cover this symbol'?

## Answer

No — and the first diagnosis was wrong. affected DOES link tests (affected '_state' -> 9 test fns under tests/; a conftest fixture reaches 17 across two modules). The cause is that _SELF_TREES runs graphify extract TWICE and merge-graphs re-namespaces node ids per merge, leaving disjoint namespaces (knowledge-base::python:: vs tests::) that no edge can span: 3368 tests-touching edges, 0 crossing, control 2194 within python/. Decisive arm: cognee, extracted in ONE run, has 10099 test<->src edges in the same graph file. A config gap of ours, not a tool gap. Filed as #101; the combined-extraction fix is UNVERIFIED.

## Outcome

- Signal: corrected
- Correction: The first diagnosis — that graphify affected cannot link tests to the symbols they cover — was wrong. affected DOES link tests (affected '_state' reaches 9 test functions; a conftest fixture reaches 17 across two modules). The real cause is OURS: _SELF_TREES runs graphify extract TWICE and merge-graphs re-namespaces node ids per merge, leaving disjoint namespaces (knowledge-base::python:: vs tests::) that no edge can span — 3,368 tests-touching edges, 0 crossing, control 2,194 within python/. Decisive arm: cognee, extracted in ONE run, carries 10,099 test<->src edges in the same graph file. A config gap of ours, not a tool gap. Filed as #101; the combined-extraction fix is UNVERIFIED.