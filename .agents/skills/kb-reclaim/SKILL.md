---
name: kb-reclaim
description: Survey and reclaim disk space on this machine — docker images and VM disk images, local LLM weights (ollama and friends), regenerable caches (Library/Caches, .cache, bun, npm, Homebrew), superseded mise tool versions, and stale installers in Downloads. Reports by default; deletes only on an explicit --apply. Use this whenever the user asks what is eating their disk, wants space freed or cleaned up, says they are running low on space or out of room, needs room for a large download or model, mentions old or unused docker images/containers/volumes/build cache, leftover model weights, a bloated Downloads folder, or asks how much space could be recovered — and also before any multi-gigabyte download, to check whether it will fit.
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

## ⚠️ Read the SIZES from `uv run`, not from `mise run`

```bash
uv run kb-setup reclaim          # same report, TRUSTWORTHY DIGITS
```

`mise run` redacts secrets by **literal substring**, and short secret values
match ordinary digits — so every figure a `mise run` task prints can come back
mangled. This tool exists to produce numbers you act on, which makes it one of
the worst places for that.

Found by the skill's own eval: an agent running this skill hit it unprompted and
re-ran through `uv run` to get real figures. The skill had been telling it to
read numbers the repo already knew were untrustworthy. `mise run` stays correct
for *doing* the work (and for `--apply`); read the SIZES from `uv run`.

```bash
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
| `jetbrains_support` | `dirs` | per-IDE-version plugins/indexes/settings left by old installs |
| `jetbrains_apps` | `dirs` | **disabled by default** — Toolbox-installed IDEs; removing one is an *uninstall*, not a reclaim |

One category per artifact type on purpose: a lumped `caches` block was
all-or-nothing, so you could not keep bun's cache while dropping npm's.

Every one can be disabled, re-scoped or re-thresholded in `reclaim.toml` without
touching python. `--only` / `--skip` narrow a single run.

## Deep gotchas — read before changing how anything is measured

Four defects reached commits here with all gates green, and each left a rule in
the code that will look arbitrary until you know why. **`references/gotchas.md`**
has them in full; the one-line versions:

1. **A `dirs` category deletes ENTRIES, never the root.** The first version
   emitted the configured root, so `--apply` would have `rmtree`d all of
   `~/Library/Caches`. 17 tests were green over it.
2. **A container disk image is SPARSE.** `Docker.raw` advertises 1858.2G while
   occupying 285.8G. Measure allocated bytes; `du -sk` does it natively.
3. **Pruning docker does not shrink that file on macOS.** The image is reported
   as context and excluded from the total.
4. **There may be more than one container engine.** This machine had Docker
   Desktop *and* a dormant colima VM holding 41G.

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

**Three states, kept distinct — this is the part to actually read.** Collapsing
them is how every reporting defect in this tool happened:

| line | means |
|---|---|
| `nothing found — scanned, not skipped` | the scan ran and the category is genuinely empty |
| `COULD NOT CHECK — <reason>` | a path is missing, a binary is absent, a daemon is down. **Not a clean result** |
| `nothing found in what COULD be checked` | both: part of the category was unreachable |

A run with anything unreachable ends with `N thing(s) COULD NOT BE CHECKED … the
total above is a floor, not the answer`. A headline number computed over an
incomplete scan has to say so, or a typo in `reclaim.toml` reads exactly like an
empty cache.

- `--only` matching no category exits **2**. A filter that asked nothing is a
  malformed request, not an empty success.
- Findings under `min_size_mb` are **dropped, not summed** — they are neither
  listed nor in the category total, so the headline number is a floor with
  respect to that threshold too. Only the listing *tail* is summed-but-unlisted
  (12 print, the rest report as "… and N more totalling X").

## One thing to know if you edit the guard

`kb_setup.hook_guard.decide()` is shared with `kb_setup.skill_lint.check()` —
one decision function, enforced at runtime **and** at authoring time. So the
bare-interpreter denial added 2026-08-07 also means a bare `python`/`python3`
inside a ```bash fence in any `SKILL.md` fails `mise run lint`, not just a live
Bash call. That is intended — a skill that *instructs* a bare interpreter is
teaching the thing the guard exists to stop — but it is a second blast radius
the change's own commit did not mention, so it is written down here.

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

- `references/gotchas.md` — the four defects that reached green commits.
- `reclaim.toml` — the whole policy surface, commented.
- `.Codex/rules/use-tool-builtins.md` — why the docker path prunes natively and
  reports rather than inventing a compaction.
- `.Codex/rules/probes-need-a-control-arm.md` — why the sparse-file test skips
  instead of passing when it cannot discriminate.
