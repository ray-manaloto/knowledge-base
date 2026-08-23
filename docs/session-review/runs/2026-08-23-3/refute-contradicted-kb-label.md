# Refutation lane: kb-label "can never exit 0 on its own documented default path"

Started. Primary artifacts read:
- CLAUDE.md:87 — "**Label** after every merge: `mise run kb-label` — deterministic hub labels (no LLM, Gemini-free). Do not expect LLM-named communities (claude-cli #2076)."
  NOTE: this line says nothing about *stderr*. It is about community NAMES.
- python/src/kb_setup/graphify_ops.py `_run` inside label: rc==0 + non-empty stderr -> events.fail("label.stderr") -> return 3.

Open questions to probe:
1. What were the ACTUAL stderr bytes in the reproduced run? Is it the "no LLM backend" notice, or something else (e.g. zero-node warnings)?
2. Is stderr NECESSARILY non-empty on the deterministic path? (the "can never exit 0" universal)

## Established (primary artifacts, not the transcript)

1. **The stderr is EXACTLY the no-LLM notice, byte-for-byte.** graphify/llm.py:3385-3389
   (installed, .venv/lib/python3.14/site-packages/graphify) prints ONE line:
   `[graphify label] no LLM backend configured; keeping Community N placeholders. Set an API key (e.g. GOOGLE_API_KEY) or pass --backend.`
   Computed length = **134 bytes with newline** — identical to the `stderr_bytes=134`
   in the refusal message quoted in issue #442. So the reported stderr contained
   that line and NOTHING ELSE. The finding's causal identification is exact.
2. **The guard is unconditional.** graphify_ops.py:479-488 — `if result.stderr:` with
   no allowlist -> `return 3`. `_labelled()` returns rc unchanged (its own docstring:
   "The failing rc is the caller's job, and returning it unchanged says so").
3. **The sibling has the identical shape**: graph.py:459-464 raises SystemExit on
   rc==0 + any stderr. No allowlist there either.
4. `ANTHROPIC_API_KEY` is NOT present in this environment (checked by NAME only).
   `clean_env()` (graphify_env.py:25-51 + comment at :20-24) deliberately KEEPS
   ANTHROPIC_*; every other backend trigger is stripped. detect_backend()
   (llm.py:3069-3087) therefore returns None here.

## Correction to the finding's wording (not a refutation)

CLAUDE.md:87 says nothing about *stderr*. Verbatim: "**Label** after every merge:
`mise run kb-label` — deterministic hub labels (no LLM, Gemini-free). Do not expect
LLM-named communities (claude-cli #2076)." The finding paraphrases this as "tells
every agent to expect kb-label's no-LLM-backend stderr notice as normal". It
documents the no-LLM path as the expected DEFAULT; it does not name the stderr byte.

## The two arms (in-process, graph.json untouched)

Script: scratchpad/armdir/arm_label_stderr.py — applies `kb_setup.graphify_env.clean_env()`
to os.environ, then calls `graphify.llm.generate_community_labels` on a 2-node graph.

ARM A (repo's real default env):
    detect_backend() -> None
    source -> placeholder
    STDERR_BYTES = 134
    STDERR_REPR = '[graphify label] no LLM backend configured; keeping Community N placeholders. Set an API key (e.g. GOOGLE_API_KEY) or pass --backend.\n'

ARM B (CONTROL — same probe, ANTHROPIC_API_KEY set to a fake value):
    detect_backend() -> 'claude'
    STDERR_BYTES = 404
    STDERR_REPR = "[graphify label] batch 1/1 (2 communities) failed: Error code: 401 …\n[graphify label] warning: community labeling failed (…); using Community N placeholders.\n"

=> The probe DISCRIMINATES: the 134-byte no-LLM line is emitted only when
detect_backend() returns None. ARM A's 134 bytes match `stderr_bytes=134` in the
refusal exactly.

## Why the default path cannot avoid it

- graphify/cli.py:1748 `force_relabel = cmd == "label"` — the `label` subcommand
  ALWAYS skips the reuse branch (:1906 `if labels_path.exists() and not force_relabel`)
  and takes the else at :1986.
- graphify/cli.py:2010-2014 calls `generate_community_labels(...)` with **no `quiet=`
  argument** -> `quiet=False` -> llm.py:3385 prints unconditionally when backend is None.
  `--missing-only` does not skip the call (:2000-2009 only narrows its input dict).
- kb_setup/cli.py:213 `claude_cli="--claude-cli" in rest` -> bare `mise run kb-label`
  takes graphify_ops.py:491 `if not claude_cli:` — the branch its own comment (:493)
  calls "The clean default".
- graphify_ops.py:481-488 -> `return 3`. `_labelled()` returns rc unchanged.

Artifact check (wrong-artifact guard): `graphify_exe()` returns `.venv/bin/graphify`;
`.venv/bin/graphify --version` = **graphify 0.9.48** = the pyproject pin (:32);
PATH resolves to the same binary. Source read from
`.venv/lib/python3.14/site-packages/graphify` — the same install.

## VERDICT: refuted = FALSE. The finding stands.

## Two corrections to its wording (neither refutes it)

1. CLAUDE.md:87 never mentions stderr. It documents the no-LLM default as expected;
   it does not "tell every agent to expect the stderr notice". The contradiction is
   real (documented-normal path vs fatal refusal) but the doc line is about
   community NAMES.
2. "can never exit 0" is true **while detect_backend() returns None**, not by
   construction. `clean_env()` deliberately KEEPS ANTHROPIC_API_KEY/ANTHROPIC_BASE_URL
   (graphify_env.py:20-24), so a host with a WORKING Anthropic key takes the LLM path
   and never emits the 134-byte line. Verified `ANTHROPIC_API_KEY` is ABSENT here, so
   the claim holds for this repo as configured. Issue #442's stronger sentence — "There
   is no configuration reachable from this repo in which the default path exits 0" — is
   the one overstatement: that configuration IS reachable and is deliberately preserved.
   (ARM B also shows a *failing* key still writes stderr -> still rc 3, so only a
   working key would reach rc 0 — and that is not the documented no-LLM default.)

## Cross-claims verified

- #438 (CLOSED) is exactly the shape claimed: `tool_sync.py _checked()` any-stderr
  refusal meeting `mise lock`'s own stderr progress; fixed with a bounded recogniser
  (`_mise_progress_only`). So the repo already ships the remedy pattern that
  graphify_ops.label lacks.
- graph.py:459-464 carries the identical unconditional shape (raises SystemExit).

## No other finding in the set contradicts this one.
Finding 12 (CLAUDE.md:177 says 0.9.45, pyproject:32 pins 0.9.48) is adjacent and
INDEPENDENTLY CONFIRMED here as a side effect: pyproject.toml:32 = 0.9.48.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issues #442, #438; the code under review.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — installed 0.9.48 `llm.py` / `cli.py` read as the primary artifact.
# Refutation attempt: kb-label can never exit 0 on its documented default path

Commit under review: repowise-mcp-0821. Findings written as probes ran.

## Probe 1 - graphify_ops.label() has no stderr allowlist (source read)
python/src/kb_setup/graphify_ops.py:475-488 (_run inside label()):
  if result.returncode != 0: return result.returncode
  if result.stderr: events.fail("label.stderr", ...); return 3
  return 0
Default branch is `if not claude_cli:` at :495 -> _run(base=[exe,"label","."]).
No allowlist, no filter. CONFIRMS the finding's code half.

## Probe 2 - does graphify label ALWAYS write stderr on the no-backend path?
installed graphify 0.9.48 (.venv/bin/graphify, mise exec -- graphify --version = 0.9.48)
- cli.py:1748  force_relabel = cmd == "label"   -> `graphify label .` ALWAYS forces
- cli.py:1906  reuse branch is `if labels_path.exists() and not force_relabel` -> SKIPPED for `label`
- cli.py:2010  else-branch calls generate_community_labels(...) with NO quiet= kwarg
- llm.py:3369  quiet default False
- llm.py:3383-3389  `if not backend: if not quiet: print("[graphify label] no LLM backend
  configured; keeping Community N placeholders...", file=sys.stderr)`
So stderr is non-empty on every default-path run => label() returns 3.

## Probe 3 - could a backend be detected (the one way to skip that print)?
detect_backend() (llm.py:3058-3088) priority gemini,kimi,claude,openai,deepseek,azure,bedrock,ollama.
clean_env() (graphify_env.py:25-51) strips GEMINI/GOOGLE/KIMI/OPENAI/DEEPSEEK/AZURE/AWS_*/OLLAMA_*
but KEEPS ANTHROPIC_*. Presence probe (values never printed):
  ANTHROPIC_API_KEY absent, ANTHROPIC_AUTH_TOKEN absent, CLAUDE_API_KEY absent,
  GEMINI_API_KEY SET, AWS_REGION SET (both stripped by clean_env).
=> detect_backend() returns None here. No escape on this host.

## Probe 4 - a SECOND, independent stderr source exists
mise exec -- graphify query "labels" --graph graphify-out/graph.json --budget 100 (stderr to file):
  164 bytes: "[graphify] note: this graph uses the pre-#1504 node-ID scheme; rebuild with
  `graphify extract --force` to get path-qualified IDs (fixes same-name-file collisions)."
Source cli.py:1057. So even if the no-backend notice were silenced, this graph still
emits stderr on load.

## Probe 5 - END-TO-END on the REAL pinned binary (throwaway graph, repo untouched)
Scratch dir with graphify-out/graph.json (3 nodes, 2 links), pyproject.toml copied,
.venv symlinked to the repo's. Invoked the SAME console script mise.toml:911 runs
(`uv run kb-setup label` -> .venv/bin/kb-setup label), cwd = scratch (cli.py:104
repo_root = Path.cwd()):

  env -C "$S" "$R/.venv/bin/kb-setup" label
  REAL rc=3
  stderr:
    [graphify] Extraction warning (3 issues): ...
    [graphify label] no LLM backend configured; keeping Community N placeholders. ...
    ERROR: [kb-label] refusing warning-bearing Graphify success
      (stderr_bytes=276, stderr_sha256=7673f549...)
  stdout ended: "Done - 1 communities. GRAPH_REPORT.md, graph.json and graph.html updated."

Bare binary, same dir, twice: `graphify label .` rc=0 with 366 then 276 stderr bytes.
The no-backend notice survives run 2 (labels already existed) because cli.py:1748
sets force_relabel for cmd=="label", so the reuse branch is unreachable.

## CONTROL ARM - the probe has two faces
Same entry point, same scratch repo_root, only the graphify binary swapped for a stub
that prints to STDOUT ONLY and exits 0 (answering --version 0.9.48 to clear the
pin check):
  CONTROL-ARM rc=0    stderr: (empty)
  stdout: "... Done - 1 communities ..." + "[kb-prose] graph-prose.json: 3/3 nodes ..."
So `kb-setup label` DOES return 0 when stderr is empty. rc 3 vs rc 0 turns on exactly
the stderr byte. A second control: `graphify --version` under the identical capture
shape -> 0 stderr bytes, so the stderr-capture probe is not stuck on one face.

## VERDICT: NOT REFUTED
The finding's operational claim is reproduced end-to-end.

Precision notes (do not change the verdict):
- The finding paraphrases CLAUDE.md:87 as a "stderr notice". CLAUDE.md:87 actually
  says "Do not expect LLM-named communities (claude-cli #2076)" - about the OUTPUT,
  citing a claude-cli defect. The string that really fires is llm.py:3387
  "[graphify label] no LLM backend configured; keeping Community N placeholders."
  Different message, different cause. The contradiction stands anyway: CLAUDE.md:86
  prescribes `mise run kb-label` as the "Label after every merge" default step.
- TWO independent stderr sources make rc=3 unavoidable on the real corpus graph:
  the no-backend notice AND cli.py:1057's pre-#1504 node-ID note (measured 164 bytes
  on graphify-out/graph.json). Silencing one would not restore rc=0.
- One boundary on "never": clean_env deliberately KEEPS ANTHROPIC_*, so on a host
  with ANTHROPIC_API_KEY set detect_backend() returns "claude" and the notice is
  skipped. That host is not running the documented deterministic no-LLM default,
  and this host has no ANTHROPIC_* set (presence-probed with [[ -v ]], values never
  printed).
- No other live finding this round touches kb-label; nothing contradicts.
