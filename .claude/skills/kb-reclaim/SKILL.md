---
name: kb-reclaim
description: Find and reclaim large disk artifacts on this machine — container images and VM disks, local model weights, regenerable caches, superseded toolchain versions, stale installers. Use whenever the user asks what is eating disk, wants space freed, is short of room for a download, mentions old docker images/containers/volumes, leftover ollama or other model weights, a full Downloads folder, or asks how much space could be recovered. Reports by default and deletes only on an explicit --apply.
---

# kb-reclaim

One command answers "what is eating my disk, and what can safely go":

```bash
mise run kb-reclaim
```

It **reports and deletes nothing**. Reclaiming is always an explicit second act:

```bash
mise run kb-reclaim -- --apply
mise run kb-reclaim -- --only docker,ollama --apply
mise run kb-reclaim -- --skip caches_system
```

Policy lives in **`reclaim.toml`** at the repo root; the engine is
`kb_setup.reclaim`; the seam is the mise task (`zero-bash-logic.md`,
`mise-tasks-only.md`). Adding a reclaimer is a scanner plus a config block —
**docker cleanup is one category, not the tool.**

## Shipped categories

| category | `kind` | what it finds |
|---|---|---|
| `docker` | `docker` | per-engine reclaimable images / build cache / volumes / containers, plus each engine's host-side disk image |
| `ollama` | `ollama` | local model weights older than `age_days`, with a `keep` allowlist |
| `caches_system` | `dirs` | entries in `~/Library/Caches` untouched for `age_days` |
| `caches_xdg` | `dirs` | entries in `~/.cache` untouched for `age_days` |
| `caches_bun` | `dirs` | `~/.bun/install/cache` — `whole_tree`, see below |
| `caches_npm` | `dirs` | `~/.npm/_cacache` — `whole_tree`, see below |
| `homebrew` | `homebrew` | `brew cleanup --prune`: stale downloads AND superseded Cellar versions |
| `mise_installs` | `mise_versions` | superseded tool versions, keeping pinned + N newest |
| `downloads` | `files` | installers/archives over a size and age threshold |

One category per artifact type on purpose: a lumped `caches` block was
all-or-nothing, so you could not keep bun's cache while dropping npm's.

Every one can be disabled, re-scoped or re-thresholded in `reclaim.toml` without
touching python. `--only` / `--skip` narrow a single run.

## The three things that will bite you

### 0. A `dirs` category deletes ENTRIES, never the root — and this was a near-miss

The first version emitted the **configured root itself** as a finding and never
read `age_days`, so `--apply` would have `rmtree`d the whole of
`~/Library/Caches`, `~/.cache`, `~/.bun/install/cache` and `~/.npm/_cacache`
— caches of running apps included — while every category's config advertised a
30-day window. `_guard_path` permitted it because `rr in (resolved, *parents)`
is true on equality. **17 tests and four gates were green over this**; they only
ever asked "inside the root" vs "outside the root", never whether the boundary
itself was excluded.

Now: `_guard_path` refuses `target == root`, and `scan_dirs` emits per-entry
findings filtered by `find -newermt <absolute timestamp>` — absolute because the
relative form errors outright on this machine and silently matches nothing on
BSD `find`, which would mark a live cache as stale. A staleness probe that
**fails** returns "recent", never "safe to delete".

**`whole_tree = true`** opts one category out of the age check, for
content-addressed caches (`_cacache`) whose top-level directories every install
touches — an age-filtered scan reports `0B` there forever. It is off by default
and must be written per category: "delete regardless of age" is the behaviour
that made the first version dangerous, so it is now a stated choice.

### 1. A container disk image is SPARSE — never trust its apparent size

This is not a footnote; it is the defect this module shipped with and the reason
the sizing code looks the way it does. `Docker.raw` on this machine reports
**`st_size` 1858.2G** while occupying **`st_blocks*512` 285.8G**, which is what
`du` agrees with. Summing `st_size` produced a first live run claiming
**2343.4G reclaimable on a 1.8TB disk** — arithmetically impossible, and stated
with total confidence.

So `reclaim._allocated` measures `st_blocks * 512` everywhere, and
`tests/test_reclaim.py` pins it with a control arm that **skips** if the
filesystem under test did not actually produce a sparse file. If you add a
scanner, measure allocated bytes; `path.stat().st_size` is the wrong call.

### 2. Pruning docker does NOT shrink the file macOS reports

The engine's storage lives *inside* that one sparse image. `docker system prune`
frees space **inside** it; the host file usually does not shrink. So the tool
prints two numbers per engine and refuses to conflate them:

- **`Images reclaimable`** etc. — from `docker system df`, what is free inside;
- **`disk image on host`** — marked `(context, not counted)`, and deliberately
  **excluded from the reclaimable total**, because those are the same bytes.

After `--apply`, `_image_delta_line` re-measures and says plainly whether the
file moved. If it did not, it says so and names the manual path (Docker Desktop
→ Settings → Resources, or Troubleshoot → Clean/Purge data). **This tool does
not rewrite a live VM disk** — there is no `docker` subcommand for it on macOS,
and hand-rolling one is exactly what `use-tool-builtins.md` forbids.

### 3. There may be more than one container engine

Check before concluding. This machine had **Docker Desktop (286G)** *and* a
dormant **colima VM (41G)** — and colima was not even runnable (`mise` had no
version set for the shim), so 41G was sitting there from an abandoned setup.
`docker context ls` is the probe; add one `[[category.docker.engines]]` block per
engine you find.

## Safety, and how it is enforced

- **Dry run is the default, and no config key can change that.** `--apply` is
  required on every run. A deleter whose destructive mode can be armed from a
  config file is a destructive action at a distance.
- **A category acts only inside its own declared roots**, never inside this
  repository, never the filesystem root. `_guard_path` refuses anything else, so
  a typo in `reclaim.toml` fails closed. Tested in **both** directions — the
  refusal asserts the file survives, and a control-arm test proves an in-root
  deletion really does happen (`probes-need-a-control-arm.md` rule 2).
- **ollama models go through `ollama rm`, never by deleting blobs.** Blobs are
  content-addressed and shared between models; removing one by hand corrupts
  every model that references it.
- **Anonymous docker volumes are OFF by default.** Unlike an image, a volume is
  the only copy of whatever is in it, and `docker system df` cannot tell you what
  that is.

## Reading the report

- A category with no hits prints `nothing found — scanned, not skipped`. That
  distinction matters: a scanner that never ran is not a clean result.
- `--only` matching no category exits **2**. A filter that asked nothing is a
  malformed request, not an empty success.
- Findings under `min_size_mb` are summed into the category total but not listed.

## Before a large download

The reason this exists. To know whether something fits:

```bash
df -h /                        # what you have now
mise run kb-reclaim            # what you could have
```

Colibri's weights are the worked example — its models range from ~4 GB (OLMoE)
to ~1.6 TB (Kimi K3), and on a 96 GB machine the binding constraint is disk, not
RAM, because routed experts stream from storage.

## See also

- `reclaim.toml` — the whole policy surface, commented.
- `.claude/rules/use-tool-builtins.md` — why the docker path prunes natively and
  reports rather than inventing a compaction.
- `.claude/rules/probes-need-a-control-arm.md` — why the sparse-file test skips
  instead of passing when it cannot discriminate.
