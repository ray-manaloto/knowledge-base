---
type: "query"
date: "2026-08-11T19:23:10.720169+00:00"
question: "What did the Graphify 0.9.40 currency and rebuild loop teach us about version parity and legacy-ID warnings?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["graphify", "graphify_env"]
---

# Q: What did the Graphify 0.9.40 currency and rebuild loop teach us about version parity and legacy-ID warnings?

## Answer

Graphify upgrades require three independent identities to agree: the mise CLI,
the SDK interpreter recorded in graphify-out/.graphify_python, and the aggregate
currency stamp. A CLI-only check missed a stale 0.9.39 SDK until a real
transcription/control path exercised the import. The interpreter marker must be
re-resolved when its installed distribution version differs from the pin.

Graphify 0.9.40 can also emit a false pre-#1504 node-ID warning on a freshly
forced aggregate: graph_has_legacy_ids compares the merge namespace prefix
(for example agnix::) with a source stem and mistakes the namespace for a legacy
ID. A fresh path-qualified node and its source_file are the discriminating
control; rebuilding the same graph again does not address this warning.


## Outcome

- Signal: useful

## Source Nodes

- graphify
- graphify_env