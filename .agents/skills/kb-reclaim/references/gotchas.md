# kb-reclaim — the four defects this tool shipped with, and what they cost

Read this before adding a scanner, changing how anything is measured, or
believing a number this tool prints. Each entry is a defect that reached a
commit with green gates, so each is a shape to check your own change against
rather than a historical note.

### 0. A `dirs` category deletes ENTRIES, never the root — and this was a near-miss

The first version emitted the **configured root itself** as a finding and never
read `age_days`, so `--apply` would have `rmtree`d the whole of
every path the `caches_*` categories declare — caches of running apps included
— while every one of those categories advertised a 30-day window. `_guard_path` permitted it because `rr in (resolved, *parents)`
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
