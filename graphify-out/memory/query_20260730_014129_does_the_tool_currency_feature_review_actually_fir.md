---
type: "query"
date: "2026-07-30T01:41:29.076453+00:00"
question: "Does the tool-currency feature review actually fire on real release notes?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does the tool-currency feature review actually fire on real release notes?

## Answer

No — it was structurally dead. 0 matches on all three real corpora (mise v2026.7.16: 10.8KB with nine '## Added' bullets scored zero; graphify 0.9.27-0.9.30; claude-code 2.1.220) while its unit tests passed, because every fixture was written in the one format the detector understood (conventional-commits 'feat:' and prose phrases). Fixed by making it section-aware (Keep-a-Changelog / GitHub-generated '## Added'/'## Highlights'), per-release rather than per-body, plus an explicit third state for notes whose format is unreadable.

## Outcome

- Signal: useful