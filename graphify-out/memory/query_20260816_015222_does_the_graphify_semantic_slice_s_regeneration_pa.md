---
type: "query"
date: "2026-08-16T01:52:22.647914+00:00"
question: "Does the graphify semantic slice's regeneration path still work, or does only its verifier still pass?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does the graphify semantic slice's regeneration path still work, or does only its verifier still pass?

## Answer

No -- it had been broken since #309, and the verifier could not see it.

#309 made KB_SEMANTIC_PROVIDER_BOUNDARY_PATH mandatory in the SHARED
graphify_semantic_adapter.adapter_main, and migrated only the corpus launcher.
Every slice run since then failed with "provider boundary marker path is unset".

Nothing noticed because "kb-graphify-semantic-slice verify" reads the COMMITTED
artifacts, which #308 had already produced. The generator was dead while its
verifier stayed green.

The generalisable shape: a verifier over committed evidence does not exercise the
path that produced it. Any module with a run verb and a verify verb where verify
reads artifacts on disk has this hole by construction. Three such pairs exist
here -- baseline, semantic slice, semantic corpus.

Fixed by convergence rather than by making the marker optional: nothing checks
after the fact that the marker was written, so "absent means skip" would let a
corpus run that merely FORGOT the variable lose its boundary evidence in silence.
The slice now sets the path and retains provider-boundary-start.json as a
candidate member, so it gains provider-call evidence it never had. Tracked as
issue #320.


## Outcome

- Signal: useful