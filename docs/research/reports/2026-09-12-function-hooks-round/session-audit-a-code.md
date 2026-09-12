# Session audit A — shipped-code correctness

Audit target: `4cdd8bfb` (`4cdd8bfbc3a2d7919adc8057c34afd487813fa26`), branch `feat/754-plugin-types-contract`.

## Scope and evidence discipline

- Cold audit of the five requested implementation, test, arm, wiring, and consumer surfaces.
- Repository state at start: HEAD exactly matched the target SHA. The two pre-existing untracked files were `docs/artifacts/function-hooks-work-order.html` and `docs/direction/2026-09-12-ray-directives.md`; this lane did not modify them.
- Graph-first lookup was attempted before source inspection. The broad query returned Graphify `rc=0` internally but the health wrapper returned `rc=3` because the answer was truncated to 56 of 2,536 nodes. Three path-narrowed queries also returned wrapper `rc=3` and truncated results (56/912, 63/173, and 67/376). All four runs warned that the graph uses the pre-#1504 node-ID scheme and should be rebuilt with `graphify extract --force`; each also emitted `mise WARN tool purgatory cleanup failed: Operation not permitted (os error 1)`. The graph did not orient this audit to the new files, so the analysis below uses the requested source paths as fallback authority. No absence claim is based on these graph results.

## Findings (incremental)

## A4 — focused suite and live task

- Focused suite command: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' UV_CACHE_DIR=/tmp/kb-audit-a-uv-cache uv run pytest tests/test_mod_runtime.py -q`. Result: 26 tests passed, `rc=0`.
- Live command: `mise run kb-mod-runtime-check` with `PYTHONDONTWRITEBYTECODE=1` and the uv cache redirected under `/tmp`. Result: `rc=0`. Real captured output (the PTY itself shortened the task-prefix command with an ellipsis):

  ```text
  mise WARN  tool purgatory cleanup failed: Operation not permitted (os error 1)
  [kb-mod-runtime-check] $ uv run --project /Users/rmanaloto/dev/github/ray-manal…
  [mod-runtime-check] clean: generated the declarations live at 2.1.269 (Claude Code), which wrote exactly the 2 expected artifacts, and all 11 symbols mechanically derived from register.ts are declared by that runtime. NOT proven here: that those symbols appear in the right POSITION, or that the mod's hook fires at all — this reads declarations, it does not run the guard (see #757).
  [mod-runtime-check] (informational) vendored claude-code-function-hooks-types.d.ts: 7966 lines vs 9263 generated
  rc=0
  ```

- A `find . -type f -newer <pre-run-stamp>` observation saw one repository path change during the command window: `.agent/kb/reports/agents/graphify-extraction-owner.md`. It was a pre-existing report outside this gate's code paths, and another workspace actor may be active, so this observation does **not** establish that the gate wrote it. The generated declaration files themselves were created inside a unique `TemporaryDirectory` and removed on return; no `.claude/types` outputs remained in the repository. Attribution of the unrelated report mtime is unverified.

### P1 — The task has an undeclared function-hooks environment prerequisite and misclassifies its absence

The claim that the live check “genuinely needs the binary” is incomplete. `/plugin-types` is unavailable unless `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` is present in this installation. The task wiring does not set that variable (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/mise.toml:1928`), while the module inherits the ambient environment when invoking Claude (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:397`).

Paired live arm, same resolved 2.1.269 binary, same fresh empty `HOME`, same minimal environment, only the feature flag changed:

- Flag absent: Claude itself returned `rc=0`, printed `Unknown command: /plugin-types`, and wrote no files. `mod_runtime.check` returned `Rc.FINDINGS` (`1`) and printed only the two `EXPECTED OUTPUT NOT WRITTEN` lines.
- Control with `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`: `mod_runtime.check` returned `Rc.OK` (`0`), derived 11 symbols, and reported 9,115/10 lines for the two generated files under the sterile home.

Cause: successful-process stdout/stderr is discarded before the topology verdict. Output is printed only for a nonzero child rc at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:518`; the missing-file branch at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:526` cannot reveal `Unknown command`. Thus clean CI with Claude installed but the flag absent reads as a contract regression (`1`), not “the question was never asked” (`127`), and hides the actionable cause. This directly contradicts the binary-only statements at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:15`, `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/gates.py:207`, and `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/mise.toml:1940`.

### P1 — The mechanically derived set silently shrinks under realistic TypeScript, refuting “a new field joins with no edit”

The extractor recognizes dotted property access, double-quoted literal `on(...)`, a shallow double-quoted matcher shape, and line-start unquoted `key:` forms (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:144` through `:174`, consumed at `:293` through `:308`). It refuses only when the result falls below six tokens or loses the single `agentId` anchor (`:306`). That is not enough to make derived completeness self-maintaining.

The current set was independently re-derived as exactly 11: `agentId, deny, file_path, fs, kind, list, log, name, tool, tool.call, ui`. In-memory end-to-end arms used the real `register.ts`, the real `check()` orchestration, a stub generator that wrote the expected regular files, and declaration text deliberately missing the dependency under test:

- Control: add `const permissionMode = e.permissionMode`; the set grows to 12 and declarations lacking `permissionMode` produce `Rc.FINDINGS` (`1`). Mutant: add the same dependency as `e["permissionMode"]`; the set stays at 11, the committed four-name/floor control remains satisfied, and the gate returns `Rc.OK` (`0`).
- An existing non-anchor has the same hole: destructuring `kind` from the real `dotGit.kind` use at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/mods/kb-settings-guard/hooks/register.ts:131` removes `kind` while leaving ten tokens, all four named test anchors, and the size floor intact. Declarations without `kind` therefore pass both the direct gate premise and the committed control at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/tests/test_mod_runtime.py:89`.
- A new field used only inside a template interpolation is erased with the entire template by `_TS_STRING`; the shipped consumer already accesses runtime fields inside templates at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/mods/kb-settings-guard/hooks/register.ts:161` and `:179`.
- Single-quoting `on('tool.call', ...)`, destructuring `file_path`, or placing `deny:` inline also makes the direct live gate green with a smaller set. The focused suite would catch these three current discriminators because it names `tool.call`, `file_path`, and `deny`; it would not catch the new-field/non-anchor cases above.

The unit suite's positive declarations are generated from the extractor's own result at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/tests/test_mod_runtime.py:360`, so they cannot independently prove that result complete. Two additional inert implementation mutants were executed by the cold review: disabling `_ON_MATCHER` removed `tool`, and adding real field `kind` to `_JS_BUILTIN_MEMBERS` removed `kind`; all 26 focused tests still passed in both cases. The committed arm TOML has no arm for matcher extraction or a non-anchor builtin exclusion (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/docs/research/arms/2026-09-12-g01-mod-runtime.toml:148` and `:180` cover the event literal and `agentId`, not these cases).

### P1 — Global substring presence cannot detect a field disappearing from the relevant runtime shape

`missing_tokens` searches each token anywhere in the entire declaration text (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:311` through `:336`). Its absent sentinel proves only that the matcher can return a miss; it does not prove structural or positional specificity. Paired in-memory probes returned:

```text
identifier_absent_control ['agentId']
identifier_comment_only []
identifier_unrelated_type []
```

Thus `agentId` solely in a comment or an unrelated interface satisfies the blocking check. The vendored declaration already contains independent `agentId` occurrences in several unrelated shapes, including `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/media/claude-code-function-hooks-types.d.ts:47`, `:109`, `:5416`, and `:7377`; deleting it only from the `tool.call` event can remain green. The module candidly disclaims position at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:86`, but that disclaimer also means the shipped gate cannot catch the realistic runtime break most relevant to the guard.

### P1 — The live command writes persistent Claude state outside its temporary CWD

The temp CWD does keep generated declarations out of this repository, but it does not make the Claude process side-effect-free. A paired isolated-HOME probe found:

- Control, same binary with `--version`: `rc=0`, zero files written under the fresh `HOME`.
- `mod_runtime.check`, same binary and environment: `rc=0`, but it created `.claude.json`, `.claude/backups/.claude.json.backup.<timestamp>`, and `.claude/projects/<temporary-CWD>/<session-id>.jsonl` under the fresh `HOME`.

The subprocess inherits `HOME` and the whole caller environment at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:410`. Therefore the actual A4 run can update user-level Claude state even though its declaration outputs are deleted. Exact paths written in the real home during A4 cannot be isolated from other concurrent Claude activity and are unverified. Concurrent direct invocations have unique generation directories but share `.claude.json` and its backup namespace; the module supplies no inter-process lock. Exclusion from this repository's `CONCURRENT_SAFE` set serializes only the gate runner's own schedule, not unrelated Claude processes.

### P2 — A test named “matched whole” accepts a containing dotted event name

For dotted tokens `_token_pattern` returns an unbounded escaped substring regex (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:327`). The test at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/tests/test_mod_runtime.py:240` checks exact `tool.call` and unrelated `tool.result`, but not a containing name. Direct paired evidence:

```text
event_absent_control ['tool.call']
event_near_collision []          # declarations contain only "tool.callback"
event_exact_control []
```

A runtime replacing `tool.call` with `tool.callback` can therefore satisfy the required `tool.call` token. The test name/docstring overstates what it asserts.

### P2 — The documented “version-only” decomposition is numerically false

The shipped module says the version-only delta is 1,190 and the remaining environment contribution is 107 (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:82`). Controlled generation used both installed binaries, separate fresh `HOME`s, otherwise identical sterile environments, and only `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`:

| Binary / artifact | Lines | SHA-256 |
|---|---:|---|
| 2.1.267 primary | 7,930 | `1128ff2ea444a25270dee36018de6f95517c39d35e75fa0ece26737176da6c64` |
| 2.1.269 primary | 9,115 | `2bb95456110eb54b4268654659bdcb935b98a4cf39f0edcd44125da5f932471b` |
| either MCP file | 10 | `47979a1cef42168e2f600c759eb3f650bc33f515baa7a9674a632db16b2533e1` |
| vendored 2.1.267 primary | 7,966 | `ed6cf189ee388d62735e39219402124eca1e40cea6139ce09776b2f006f80b1a` |

Both generation commands returned `rc=0`. The controlled version delta is **1,185**, not 1,190. The vendored artifact is 36 lines above sterile 2.1.267, while the real-HOME 2.1.269 output is 148 above sterile 2.1.269, so the observed 1,297-line delta decomposes here as 1,185 version + 112 net environment—not 1,190 + 107. The earlier 9,156 “empty HOME” measurement retained other `CLAUDE_CODE_*` environment variables and was not a sterile version-only arm. This does not affect the gate rc because the code does not gate on the figure, but it is a false measured claim in shipped documentation and the commit rationale.

### P2 — The “vendored delta” can emit a false statement and is not a general delta

`_report_vendored_delta` computes only line counts and required tokens absent anywhere in the vendored text (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:421`). It neither compares bytes nor reports arbitrary live/vendored additions such as `session.authorize`; the A4 output demonstrates that the motivating 0-vs-7 namespace difference is not reported. A missing/unreadable vendored file prints an informational message and leaves an otherwise clean gate at `Rc.OK`, which is explicit nonblocking policy rather than a hidden pass.

There is also an output-correctness bug. When live reconciliation finds a required token absent, `check` still calls the reporter (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:583`). If that token is absent from both live and vendored files, the reporter nevertheless says it is “present in the live one” (`:439`). The end-to-end control arm with `file_path` absent from both returned `Rc.FINDINGS` correctly but printed the false line:

```text
required tokens ABSENT from the vendored file, present in the live one: file_path
```

There is no focused test or mutation arm for `_report_vendored_delta`; its policy and wording are unarmed.

## A1 — behavior of each check and test soundness

### Output topology

- Realistic missing expected regular file: caught as `Rc.FINDINGS`; the focused end-to-end test at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/tests/test_mod_runtime.py:388` passed.
- Realistic stale extra regular file: caught symmetrically as `Rc.FINDINGS`; the call-site test at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/tests/test_mod_runtime.py:377` kills the arm that discards the topology verdict.
- No false-green mutant was found for the intended regular-file set in the live path. The collection is limited to `rglob('*')` entries for which `is_file()` is true (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:526`), so non-file filesystem objects are outside the measured contract.
- Test limitation: `test_the_expected_topology_reconciles_clean` passes `set(EXPECTED_OUTPUTS)` as both actual and expected (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/tests/test_mod_runtime.py:283`), and the stub writes whatever production constants currently name (`:346`). Replacing both output constants and `PRIMARY_DECLARATIONS` with invented paths left all 26 tests green. The live generator would still red, so this is an adaptive test-premise weakness rather than a live-gate false green.

### Consumer-required set

- A globally absent currently-derived token is caught as `Rc.FINDINGS`; the missing-`agentId` end-to-end test at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/tests/test_mod_runtime.py:396` passed.
- The check fails open for source shapes and position changes described in the P1 findings above. The two true inert mutants (`_ON_MATCHER` removed; non-anchor `kind` excluded as a builtin) left all 26 tests green.
- The matcher control is not tautological—it turns false if its impossible symbol is inserted—but proves only global absence capability, not positional correctness.

### Vendored reporting path

- A readable file always yields a line-count report; required tokens globally absent from it yield an additional informational line.
- Missing/unreadable evidence is reported but intentionally does not block. Arbitrary byte/content drift is not detected. The wording can be false on a live-contract failure, as armed above.

### Assertions and arm claim

An AST count found 26 test functions and at least one executable `assert` in every one; there are no zero-assert tests. Two assertions are premise-adaptive/circular in the ways noted above, and `test_a_dotted_event_name_is_matched_whole` does not test its claimed near-collision boundary. The TOML parses to one control (`A0`) and eleven mutation rows (`A1`–`A11`), all targeting `tests/test_mod_runtime.py`. I did **not** rerun `kb-arms`: it mutates tracked files and this lane expressly forbids that. Therefore “11/11 died, 1/1 control held” is **COULD-NOT-CHECK**, not re-certified from the prose claim.

## A2 — exact derivation and inherited fragility

`mod_runtime.py` uses only two attributes from `guard_inventory`: `FUNCTION_HOOK_SOURCE_PATH` at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:113`, and `strip_ts_comments` at `:293`. It does **not** call the advisor-listed `_WRITE_TOOLS_ARRAY`, `_REGISTER_LOOP`, or `function_hook_write_tools`, so it does not directly inherit those ten exact registration-loop failures. Those older regexes refuse unsupported shapes as `NOT_RUN` (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/guard_inventory.py:823` through `:887`); the new extractor instead has the silent-shrink cases already proven.

It does inherit the non-lexical comment stripper at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/guard_inventory.py:821`. Because `//` is stripped before strings, a source line containing `"https://example.test"` before a new `e.permissionMode` access erased that access from derivation; the same access without the URL was the positive control and joined the set. This is another shape where the count remains 11 and the named anchor remains present.

## A3 — non-hermetic blast radius and exact outcomes

- **Claude upgrade:** the code reports the version from one subprocess, then invokes the same unresolved path again. Same filenames plus global presence of all required strings yields `0`; changed regular-file topology or a missing required string yields `1`; launch failure, nonzero generation, or timeout yields `127`. There is no supported-version pin/range.
- **Upgrade race:** current `resolve_claude()` returns `/Users/rmanaloto/.local/bin/claude`, a mutable symlink whose current target is `/Users/rmanaloto/.local/share/claude/versions/2.1.269`. Since `--version` and generation are separate subprocesses (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:379` and `:397`), retargeting the symlink between them can attribute one version's declarations to another version. This race was reasoned from the two-call structure; it was not destructively armed.
- **Different `HOME`, inherited session environment:** fixed 2.1.269 returned `0`, producing 9,156/10 lines versus real-HOME 9,263/2,588. Both expected filenames and all 11 current tokens held.
- **Different `HOME`, sterile environment:** without the function-hooks flag the gate returned misleading `1`; with the flag it returned `0` and produced 9,115/10. Details are in the P1 environment finding.
- **No binary / CI without Claude:** paired `PATH` probe resolved the current binary in the control and `None` in the negative arm. `check()` printed `no \`claude\` binary on PATH — ... This is NOT a pass` and returned `Rc.NOT_RUN` (`127`) at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:488`. The outer runner renders any nonzero row as `FAIL` (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/gates.py:519`) but records `rc=127`, so it cannot read as a pass; overall `kb-gates` returns nonzero.
- **Concurrent runs:** generation directories are unique, but Claude writes shared HOME state. A two-process sample returned `0/0` and wrote two session JSONLs plus shared `.claude.json`/backup state; one successful sample does not certify the race safe. `kb-gates` correctly runs this task alone within one runner because it is absent from `CONCURRENT_SAFE`, but there is no cross-process lock.
- **Temp creation/cleanup failure:** `TemporaryDirectory(...)` construction/cleanup is outside the caught `subprocess` exception block. Such an `OSError` can escape as a traceback/ordinary process failure rather than the named `NOT_RUN` result. This was established by code path inspection, not a disk-failure arm.
- **Writes:** each successful call writes two declaration files in a temporary CWD and deletes them on return, but also persists the three classes of HOME files listed in the P1 side-effect finding.

The tracked `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/settings.json:4` supplies the feature flag to Claude-launched sessions. A direct `mise run kb-mod-runtime-check` from an ordinary shell does not source Claude settings; neither `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/mise.toml:1928` nor `mod_runtime.py` exports the prerequisite. A bounded search over `mise.toml` and `python/src` found only the static inventory's flag name; control search found the task/gate wiring. This repository has no `.github` directory, so no repository-local CI environment could be inspected.

## Wiring review

- CLI dispatch is present and passes both `repo_root` and remaining arguments at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/cli.py:231`; help text names the bare and `--arms` forms.
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/gates.py:215` adds the task to `GATE_TASKS`; it is absent from `CONCURRENT_SAFE`, so it forms an exclusive batch within one runner.
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/mise.toml:1928` invokes the repository project and sets an outer 360-second timeout. The wiring defect is the missing function-hooks feature flag described above.
- `--arms` delegates to the fixed committed spec, while any other argument is refused at `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:610`. The proving mode was not executed because it mutates tracked files.
- The on-disk gate receipt for the exact target SHA parses to 11 rows, each with `rc=0`, the exact SHA, and `dirty=false`. This **AGREES with the historical “Gates: 11 passed” claim from the receipt**; it is not a fresh full-gate run. A4 independently reran only `kb-mod-runtime-check`, also at `rc=0`.

One lower-severity documentation drift remains: `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/mod_runtime.py:368` says `shutil.which` currently resolves to a mise shim. Current measurement resolves `/Users/rmanaloto/.local/bin/claude`, a symlink to the 2.1.269 versioned binary; `mise which claude` returned `rc=1` and said the mise Claude binary is not active (plus the repeated purgatory-cleanup warning). Runtime selection still follows the user's actual command, so this is stale explanation rather than incorrect execution.

## A5 — commit-message claim checks

| Claim | Verdict | Re-derived evidence / bound |
|---|---|---|
| Vendored 7,966 vs installed 2.1.269 real-HOME 9,263 primary lines | **AGREES** | Fresh generation returned `rc=0`; `splitlines()` gave 9,263, and the byte-pristine vendored file gave 7,966. |
| `session.authorize` 0 vs 7 | **AGREES** | Literal occurrence count over the two exact primary files. Same-shape positive control `tool.call` counted 37 vs 46; MCP declarations contained neither token. |
| Same 2.1.269 binary, HOME-only: primary 9,263 vs 9,156; MCP 2,588 vs 10 | **AGREES** | The environment dictionaries differed only at `HOME`; both commands returned `0` and wrote exactly the two expected files. |
| Empty temp HOME, `rc=0`, both files | **AGREES only with the inherited function-hooks environment** | The original-shaped arm passes. A sterile environment disproves the broader binary-only conclusion unless `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` is supplied. |
| “11 symbols derived today” | **AGREES** | Re-derived exact set: `agentId, deny, file_path, fs, kind, list, log, name, tool, tool.call, ui`. |
| “A new field in `register.ts` joins with no edit here” | **DISAGREES** | Bracket access, destructuring, template interpolation, and the inherited comment-stripper case all leave a new field absent while the gate and committed control remain green. |
| Version-only +1,190; environment +107 | **DISAGREES** | Same sterile environment across installed 2.1.267/2.1.269 gives +1,185 version and +112 net environment for the observed +1,297 endpoints. |
| Missing binary is NOT_RUN 127, never green | **AGREES** | Paired PATH control/negative arm; exact live `check()` return was 127 and the outer gate runner records a failing row with that rc. |
| Vendored delta is informational, never blocking | **AGREES narrowly** | It never changes rc, but it is only line-count/required-token reporting, not a full delta, and one failure-path sentence is false. |
| Arms 11/11 died, 1/1 control held | **COULD-NOT-CHECK** | The TOML contains exactly those rows, but rerunning the mutation runner was forbidden because it writes tracked files. Presence of rows is not outcome evidence. |
| Gates 11 passed, 0 failed | **AGREES from the exact-SHA receipt, not live rerun** | `.agent/kb/gates/gates-4cdd8bfbc3a2d7919adc8057c34afd487813fa26.json` has 11 rc-zero, clean rows. |
| No credentials / no model call | **PARTIAL / UNVERIFIED** | Fresh HOME plus a sterile environment and only the feature flag still generated successfully, so no HOME- or environment-carried credential was needed. macOS Keychain use, network traffic, and model/token activity were not traced. |
| First sweep had four survivors and one broken probe; stale file passed every earlier gate | **UNVERIFIED** | No authoritative mutation-history or historical-gate execution record was re-run in this no-write lane. |

## What remains unverified

- General safety of two or more processes sharing a real Claude HOME; one `0/0` concurrency sample is a control, not a proof.
- Filename topology beyond the two installed versions tested here; future Claude versions may legitimately add artifacts, which intentionally reds the gate.
- macOS Keychain/network/model-call behavior of `/plugin-types`.
- The mutation sweep outcome, for the write constraint stated above.
- Which exact real-HOME state files A4 changed. Isolated HOME proved the classes of files; concurrent local Claude activity prevents attribution in the user's live home.

## Final workspace state

HEAD remains exactly `4cdd8bfbc3a2d7919adc8057c34afd487813fa26`, and `.claude/types` is absent. Control arm `find .claude/mods -type f` returned the four known mod files, so the absence probe mechanism was live.

Three tracked modifications appeared after this lane's clean start: `.claude/agents/kb-codex-advisor.md`, `.claude/agents/kb-codex-astra-advisor.md`, and `.claude/agents/kb-codex-astra-reviewer.md`. Their diffs add per-launch scratch-directory instructions and are unrelated to `mod_runtime`; this lane did not make or revert them. Their timestamps overlap this audit, so they are protected concurrent-work evidence rather than attributable gate output. The two original untracked docs also remain. This lane's only intentional repository write is this report.

## GitHub repos touched

- `ray-manaloto/knowledge-base` — audited local source at `4cdd8bfb` and read issue #754 plus advisor comment 5646259590 through authenticated `gh`.
