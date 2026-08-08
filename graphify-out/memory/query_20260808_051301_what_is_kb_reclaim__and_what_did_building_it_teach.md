---
type: "query"
date: "2026-08-08T05:13:01.192409+00:00"
question: "What is kb-reclaim, and what did building it teach about disk reclamation on macOS?"
contributor: "graphify"
outcome: "useful"
---

# Q: What is kb-reclaim, and what did building it teach about disk reclamation on macOS?

## Answer

kb-reclaim shipped 2026-08-08 (PR #237): a disk-reclamation tool as skill -> mise task -> python library. `mise run kb-reclaim` reports and deletes NOTHING; `-- --apply` reclaims; `--only`/`--skip` narrow. Policy is reclaim.toml, 11 independently-togglable categories over 6 kinds, 10 of them enabled by default (`jetbrains_apps` ships off). This record first said 9, which was wrong the day it was written — reclaim.toml already had 11 in the commit before it; re-derive with `grep -c '^\[category\.' reclaim.toml` minus the one `[category.docker.prune]` sub-table, and note that the count moves whenever a category is added. READ THE SIZES FROM `uv run kb-setup reclaim` - mise redaction mangles digits. Measured on this machine: 252.25 GB freed (480.80G -> 733.05G), plus 40.99G from a native `colima delete -d -f` teardown. Six defects reached green commits before review caught them, and the two worst were near-misses: scan_dirs emitted the CONFIGURED ROOT as a finding and ignored age_days, so --apply would have rmtree'd all of ~/Library/Caches with 17 tests and four gates green over it; and a category rooted at `/` made _guard_path vacuous because `/` is a parent of every path. Both were only found because a review ran, and the first only failed to fire because the run was killed for being slow. Other durable facts: a container disk image is SPARSE (Docker.raw advertised 1858.2G while occupying 285.8G, and summing st_size once reported 2.3TB reclaimable on a 1.8TB disk - use `du -sk`, which reports allocated blocks natively and does 21GB of tiny files in 3.5s); pruning DID shrink Docker.raw here by 101.2G, contradicting the common claim that it never does on macOS; and `docker system prune` cannot express per-type config because it always removes stopped containers and dangling images - use the per-type pruners.

## Outcome

- Signal: useful