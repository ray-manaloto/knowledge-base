---
type: "query"
date: "2026-08-20T02:20:45.864664+00:00"
question: "Does finding one predicted artifact absent prove a command did not execute?"
contributor: "graphify"
outcome: "corrected"
correction: "# The belief that was wrong: a probe that finds ONE artifact absent has proven a negative\n\nI ran a command-injection test against `xargs -I{} sh -c '{}'`, fed it\n`weird id;touch /tmp/PWNED@mkt`, saw the output truncate, checked for\n`/tmp/PWNED`, found it absent, and reported **\"no injection\"**.\n\nThe `touch` had executed. The mangled quoting simply changed which paths it\nreceived, so it created files named `-s`, `user` and `-y` **in the working\ndirectory** instead of the one file I was watching. I checked a single named\nartifact and read its absence as a general negative.\n\nThose files then broke `mise run lint` for the rest of the session — hk passes\nits file list as argv, so a file named `-y` is parsed as a flag, and twelve\nbuiltins died with `error: unexpected argument '-y' found`. I spent the next\nseveral probes hunting an environment regression that I had created, and my\nfirst hypothesis was that the plugin updates had done it.\n\n**The rule:** when testing whether something executes, do not check one expected\nside effect. Check whether the process ran at all, or diff the whole directory\nbefore and after. Absence of the artifact you predicted is not absence of the\nbehaviour — especially when the mechanism under test is one that MANGLES\narguments, where the whole failure mode is that things land somewhere other\nthan where you expect.\n\n## Five more from the same round, all the same shape: measured beats reasoned\n\n1. **\"No overlap across 13 runs\" did not replicate.** I published a clean\n   separation between two timing arms, then a confirmation batch produced a run\n   inside the old range. The effect is real (mean 1999 -> 1832 ms, medians 1994\n   -> 1817) but the distributions overlap; one run cannot show it. The wrong\n   claim had already been written into `hk.pkl`'s own comment before I\n   re-checked.\n2. **I hand-rolled instruments hk ships.** 18 timing runs off `--format json`'s\n   `duration_ms` — the wrong quantity, since it is per-command execution and\n   summing it across a parallel pipeline is meaningless. hk has\n   `HK_TIMING_JSON` (merged per-step wall time) and `hk check --plan` (prints\n   the parallel-group structure outright), both documented only in\n   `docs/logging.md`. My inferred three-phase model was correct, which is luck,\n   not method. `gitleaks` is 96% of the wall clock, not the 73% I published.\n3. **`mise -C <dir>` must precede the subcommand.** `mise run task -C dir`\n   silently ignores `-C` for task discovery. My first timeout probe returned\n   rc=1 on the arm AND both controls — a uniform result, which is the signature\n   of a broken probe, and it was.\n4. **I ran pytest concurrently with the gate's own test run**, got a git-index\n   collision in a shared clone, and nearly wrote it up as a corpus defect. Both\n   commits were present; the same test passed alone.\n5. **A filter validated in one directory.** `claude plugin list --json`'s\n   `.enabled` is evaluated against the CURRENT PROJECT: 9 from inside a repo\n   that enables plugins, **0 from `$HOME`**. I built and checked the filter in\n   the repo, so it looked right, and it made the task a silent no-op everywhere\n   it would actually be run.\n\n## And one I introduced by fixing something\n\nParallelising the plugin updates created a race: a plugin installed at two\nscopes refreshes into ONE cache directory, because the path is keyed on\n(marketplace, id, version) and that version is the literal string `unknown` for\nversionless plugins. Two workers on the same id collided with `ENOENT` on a\n`copyfile`. Identified as a race rather than breakage because both scopes\nsucceeded when run alone and the preceding run of the same 225 targets had zero\nfailures. Fixed by grouping work under plugin id.\n\n**A fix is the least-reviewed code in the diff**, and a fix that adds\nconcurrency is a fix that adds a failure mode the original did not have.\n"
---

# Q: Does finding one predicted artifact absent prove a command did not execute?

## Answer

# Round 2026-08-19e — mise 2026.8.9 + hk 1.56.0 resync, and what running things taught

## What shipped into the working tree (this repo)

- `mise` 2026.8.9 and `hk` 1.56.0 across every place each version is written.
  Ray ruled `min_version = { hard = "2026.8.9", soft = "2026.8.9" }`, overriding
  `mise.toml`'s own comment; the comment was rewritten in the same change so the
  file no longer argues against its values, and `soft` is documented as
  intentionally inert.
- `sources/mise.manifest` was pinning a **tag object**, not a commit. Control
  arm: `gh api repos/jdx/hk/commits/v1.55.0` reproduced hk's pin byte-for-byte
  while the same call for mise disagreed with the manifest. mise ships annotated
  tags, hk lightweight ones. The `git ls-remote --tags` instruction that caused
  it was rewritten in BOTH manifests.
- **Two `ref_binding` entries for `hk.pkl`** in `currency.toml`. The mechanism
  already existed (graphify declares eight); hk declared none, so the check
  reported `ref-binding | skip | this tool declares no revision bindings` — a
  SKIP whose stated reason was a true fact about the repo. It cost a live
  defect: the 1.55.0 bump moved the pin and the manifest and left `hk.pkl` on
  **v1.54.1**. Armed three ways (clean / `amends` stale / `import` stale).
- **`timeout` on 7 tasks, up from 0 of 75.** `long-running-command-hangs.md`
  rule 1 has named this mechanism since it was written — the answer to the
  7-hour hk wedge — and the repo had never adopted it.
- **`ruff_format` declared last.** `exclusive` is a whole-pipeline barrier; at
  position 15 of 20 it split the run into three phases and stranded five
  unrelated steps behind a 40 ms task.
- **`hk-test` is a gate**: `[tasks.hk-test]` -> `kb_setup.hk_test` -> 11 tests,
  added to `GATE_TASKS`, deliberately NOT in `CONCURRENT_SAFE`.
- **`lint` now emits structured output**: `HK_TIMING_JSON` + `HK_OUTPUT_FILE`
  into `.agent/kb/gates/`, armed both directions, human stdout unchanged.

## What shipped into `~/.config/mise` (chezmoi render — see CHANGES-2026-08-19.md)

`lockfile = true` + a 119-tool lockfile; `brew upgrade --yes`; `wait_for` so
brew precedes mise; the `-- --system -y` flag bug fixed; `update:claude`
rewritten in Python with a thread pool; a new read-only `update:check`;
`update:all` as the single entry point. A stale `context7-plugin` registration
was uninstalled. End state measured: 225 targets, 0 failed, 57.8s, exit 0 —
down from 211s and exit 1.

## The through-line

Almost everything of value this round came from RUNNING something, not reading
it. The resync itself was the small part; five live runs of one task each found
a defect that reasoning had not.


## Outcome

- Signal: corrected
- Correction: # The belief that was wrong: a probe that finds ONE artifact absent has proven a negative

I ran a command-injection test against `xargs -I{} sh -c '{}'`, fed it
`weird id;touch /tmp/PWNED@mkt`, saw the output truncate, checked for
`/tmp/PWNED`, found it absent, and reported **"no injection"**.

The `touch` had executed. The mangled quoting simply changed which paths it
received, so it created files named `-s`, `user` and `-y` **in the working
directory** instead of the one file I was watching. I checked a single named
artifact and read its absence as a general negative.

Those files then broke `mise run lint` for the rest of the session — hk passes
its file list as argv, so a file named `-y` is parsed as a flag, and twelve
builtins died with `error: unexpected argument '-y' found`. I spent the next
several probes hunting an environment regression that I had created, and my
first hypothesis was that the plugin updates had done it.

**The rule:** when testing whether something executes, do not check one expected
side effect. Check whether the process ran at all, or diff the whole directory
before and after. Absence of the artifact you predicted is not absence of the
behaviour — especially when the mechanism under test is one that MANGLES
arguments, where the whole failure mode is that things land somewhere other
than where you expect.

## Five more from the same round, all the same shape: measured beats reasoned

1. **"No overlap across 13 runs" did not replicate.** I published a clean
   separation between two timing arms, then a confirmation batch produced a run
   inside the old range. The effect is real (mean 1999 -> 1832 ms, medians 1994
   -> 1817) but the distributions overlap; one run cannot show it. The wrong
   claim had already been written into `hk.pkl`'s own comment before I
   re-checked.
2. **I hand-rolled instruments hk ships.** 18 timing runs off `--format json`'s
   `duration_ms` — the wrong quantity, since it is per-command execution and
   summing it across a parallel pipeline is meaningless. hk has
   `HK_TIMING_JSON` (merged per-step wall time) and `hk check --plan` (prints
   the parallel-group structure outright), both documented only in
   `docs/logging.md`. My inferred three-phase model was correct, which is luck,
   not method. `gitleaks` is 96% of the wall clock, not the 73% I published.
3. **`mise -C <dir>` must precede the subcommand.** `mise run task -C dir`
   silently ignores `-C` for task discovery. My first timeout probe returned
   rc=1 on the arm AND both controls — a uniform result, which is the signature
   of a broken probe, and it was.
4. **I ran pytest concurrently with the gate's own test run**, got a git-index
   collision in a shared clone, and nearly wrote it up as a corpus defect. Both
   commits were present; the same test passed alone.
5. **A filter validated in one directory.** `claude plugin list --json`'s
   `.enabled` is evaluated against the CURRENT PROJECT: 9 from inside a repo
   that enables plugins, **0 from `$HOME`**. I built and checked the filter in
   the repo, so it looked right, and it made the task a silent no-op everywhere
   it would actually be run.

## And one I introduced by fixing something

Parallelising the plugin updates created a race: a plugin installed at two
scopes refreshes into ONE cache directory, because the path is keyed on
(marketplace, id, version) and that version is the literal string `unknown` for
versionless plugins. Two workers on the same id collided with `ENOENT` on a
`copyfile`. Identified as a race rather than breakage because both scopes
succeeded when run alone and the preceding run of the same 225 targets had zero
failures. Fixed by grouping work under plugin id.

**A fix is the least-reviewed code in the diff**, and a fix that adds
concurrency is a fix that adds a failure mode the original did not have.
