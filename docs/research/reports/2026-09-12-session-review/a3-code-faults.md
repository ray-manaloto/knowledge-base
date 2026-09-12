# a3-code-faults — cold cross-family read of `mod_runtime.py`

Lane: **a3-code-faults** (Claude, Fable 5.1) reading codex-written code.
Commit examined: **`c1d8afb8`** (`c1d8afb8cf686a6e39f186debb0e9499d794a5dc`), branch `feat/754-plugin-types-contract`.
Fix under review: `c33a1fb5` (`python/src/kb_setup/mod_runtime.py` only — `tests/test_mod_runtime.py` was NOT touched by that commit; verified via `git show c33a1fb5 --stat`).
Mode: read-only. No tracked file modified. Revert arms are run on a scratch COPY, never via `kb-arms` (which mutates tracked files).

Question: are the three reported P1s in `mod_runtime.py` real, and is the `c33a1fb5` fix sound?

Sections are appended as each finding is reached.

## P1-1 — the derived set does not GROW under ordinary TypeScript: REAL as a false docstring claim + latent extractor gap; NOT a wrong verdict on today's `register.ts`

**Decides it.** `python/src/kb_setup/mod_runtime.py:166`
`_PROPERTY_ACCESS = re.compile(r"(?:\?\.|\.)\s*([A-Za-z_$][\w$]*)")` — dotted and optional-chained access only. `:155-159` `_TS_STRING` blanks a template literal WHOLE, `${e.x}` interpolations included. No bracket-access pattern, no destructuring pattern exists in the module.

**Measured at `c1d8afb8`** (scratch script over the committed `.claude/mods/kb-settings-guard/hooks/register.ts`, `required_runtime_tokens` unmodified):

| variant inserted after `const lane = laneOf(e);` | derived | delta |
|---|---|---|
| BASE (committed file) | **11**: `agentId deny file_path fs kind list log name tool tool.call ui` | — |
| A `const pm = e.permissionMode;` | 12 | +`permissionMode` |
| B `const pm = e["permissionMode"];` | 11 | none — INVISIBLE |
| C `const { permissionMode } = e;` | 11 | none — INVISIBLE |
| D `` $.ui.log(`pm ${e.permissionMode}`) `` | 11 | none — INVISIBLE |
| E `laneOf` rewritten as `const { agentId: id } = event;` | `None` → NOT_RUN | anchor catches `agentId` alone |
| F matcher longhand `{ tool: tool }` | 11 | none (survives via `_ON_MATCHER`) |
| G drop the `dotGit.kind` read | 10 | −`kind`, silently |
| H `// see https://example.com/x` on the line before a dotted access | 12 | +`permissionMode` — the audit's "URL erases a following access" did NOT reproduce in this shape |

So the audit's word "shrinks" is imprecise: B–D never lose today's 11, they FAIL TO GROW. The false statement is `mod_runtime.py:50-51` — *"a new field added to `register.ts` joins the contract with no edit here"* — true only for dotted/optional-chained access OUTSIDE a template literal. The committed module already sits on that edge: `e.tool` is read ONLY inside template literals (`register.ts:171`, `:190`), so it is blanked, and `tool` is in the contract solely because of the shorthand matcher `{ tool }` at `register.ts:215` → `_ON_MATCHER` → `_IDENTIFIER`.

**Failure scenario.** A later edit adds `const { permissionMode } = e; if (permissionMode === "bypassPermissions") return next(e);`. The guard now depends on `permissionMode`; the contract stays at 11; the runtime later renames the field; the gate stays green. (In that particular shape `undefined === "…"` is false, so the direction happens to be closed; the same edit on any allow-signal field is fail-open with no detector, and nothing in the module distinguishes the two.)

**Would a test catch it today? No.** `tests/test_mod_runtime.py:89` pins 4 of 11 by name plus a floor of 6. The end-to-end fixtures are built at `:362-366` FROM `required_runtime_tokens(source)` itself — structurally tautological for under-derivation: whatever the extractor fails to derive, the stub also fails to declare, and `check()` is OK. There is no constant whose change would make an existing test fail for B/C/D/G — that is the finding.

**Minimal fix, two halves.**
1. Make the derivation LOUD without a parser — pin the exact committed set (this is the half that turns "silent" into "a human reads a diff"):
```python
# tests/test_mod_runtime.py
_COMMITTED_CONTRACT = frozenset({"agentId", "deny", "file_path", "fs", "kind", "list",
                                 "log", "name", "tool", "tool.call", "ui"})
def test_the_committed_contract_is_exactly_the_pinned_set() -> None:
    source = (REPO / mod_runtime.REGISTER_TS).read_text(encoding="utf-8")
    assert mod_runtime.required_runtime_tokens(source) == _COMMITTED_CONTRACT
```
2. Either cover the three ordinary forms, or reword `:50-51` to name the supported ones. Covering them:
```python
_BRACKET_ACCESS  = re.compile(r'\[\s*"([A-Za-z_$][\w$]*)"\s*\]')       # run over no_comments (strings intact)
_DESTRUCTURE     = re.compile(r"(?:const|let|var)\s*\{([^}]*)\}\s*=")   # run over no_strings; identifiers minus builtins
_TEMPLATE_INTERP = re.compile(r"\$\{([^}]*)\}")                         # bodies pulled from each template BEFORE blanking
# in required_runtime_tokens, before/around the existing updates:
tokens.update(_BRACKET_ACCESS.findall(no_comments))
for group in _DESTRUCTURE.findall(no_strings):
    tokens.update(i for i in _IDENTIFIER.findall(group) if i not in _JS_BUILTIN_MEMBERS)
for tpl in _TS_STRING.finditer(no_comments):
    if tpl.group().startswith("`"):
        for body in _TEMPLATE_INTERP.findall(tpl.group()):
            tokens.update(p for p in _PROPERTY_ACCESS.findall(body) if p not in _JS_BUILTIN_MEMBERS)
```
Each new pattern needs its own FAIL-direction test (variants B, C, D above are the fixtures; expect `permissionMode` in the set).

## P1-2 — presence ANYWHERE in the declarations file: REAL, disclosed at `:86-97`, unmitigated

**Decides it.** `mod_runtime.py:337-341` `missing_tokens` → `_token_pattern(token).search(declarations)` over the whole file; `:316-334` `_token_pattern` is a `\b`-bounded identifier regex or a PLAIN regex for a dotted name. No comment stripping of the declarations; no scoping to the `tool.call` event type.

**Measured at `c1d8afb8`** (scratch script, `required = {"agentId"}`):

| declarations text | `missing_tokens` |
|---|---|
| `interface ToolCallEvent { file_path: string; tool: string; }` | `['agentId']` — control: the matcher CAN say absent |
| `// agentId was removed in 2.2` + the interface above | `[]` — PASSES |
| `/** the old agentId field */` + the interface above | `[]` — PASSES |
| `interface AgentStartEvent { agentId: string }` + `interface ToolCallEvent { file_path: string; }` | `[]` — PASSES |
| `tool.call` against `on("tool.callback", …)` | `[]` — PASSES (the audit's P2-5; `:332-333` has no boundary on the dotted arm) |

Against the real vendored d.ts: `agentId` is a DECLARATION at `sources/media/claude-code-function-hooks-types.d.ts:51`, `:118`, `:5429`, `:7379`, `:7438`, `:7886`, and a COMMENT mention at `:65`, `:107`, `:215`, `:5375`, `:5424`, `:5439`, `:6139`, `:6158`, `:6162`, `:7313`. The `tool.call` payload is alias-composed — `:6164` `export type ToolCallInput = ToolCallEnvelope & AgentLoop;` — so removing `agentId` from the loop type leaves ≥5 other declarations and ~10 comment mentions, and the gate is GREEN.

**Failure scenario (realistic).** Claude Code renames the `tool.call` field to `agent_id` and its generated d.ts carries the doc comment *"`agentId` is now `agent_id`"*. `register.ts:131` `laneOf` reads `undefined`, the guard allows everything (`register.ts:36-40` says so itself); the gate reads the comment and reports clean.

**Would a test catch it today? No.** `tests/test_mod_runtime.py:221` uses a declarations string with ZERO other occurrences — total absence only. `:240` `test_a_dotted_event_name_is_matched_whole` is named for a boundary it does not assert: its negative uses `tool.result`, which differs in the second SEGMENT; `tool.callback` passes. No test has "present in a comment, absent from the interface". The constant to change to make `:240` honest: `'on("tool.result")'` → `'on("tool.callback")'` — it then fails today.

**Minimal fix.**
1. Cheap half, closes the comment scenario — `missing_tokens` searches the comment-stripped text (the function is public and already imported at `:109`):
```python
def missing_tokens(required, declarations):
    visible = guard_inventory.strip_ts_comments(declarations)
    return frozenset(t for t in required if _token_pattern(t).search(visible) is None)
```
   plus a test with `agentId` only in a comment expecting `frozenset({"agentId"})`. (Note `matcher_can_report_absence` at `:344` should read the same stripped text, or its control symbol in a comment is still "present".)
2. Dotted boundary, `:333`: `re.compile(rf"(?<![\w$.]){re.escape(token)}(?![\w$])")`; and change `:243` to `tool.callback`.
3. The unrelated-interface half CANNOT be closed by regex against alias-composed types. The honest closure is the compile route the work order originally promised (the audit's "wrong statement #3"): a probe `.ts` — `declare const e: ToolCallInput; const a: string | undefined = e.agentId;` — type-checked against the generated d.ts. Positional presence is what `tsc` proves and text cannot. Whether a `tsc` is pinned here is checked below.

## The fix `c33a1fb5` — part 1: what it changes, and the revert arm

**What it changes** (`git show c33a1fb5 -- python/src/kb_setup/mod_runtime.py`, +38/−0; `tests/test_mod_runtime.py` untouched):
1. `mod_runtime.py:425` `env = {**os.environ, "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}` passed as `env=` to the `/plugin-types` subprocess (`:429`).
2. `:143` `_UNKNOWN_COMMAND = "Unknown command"`; `:550-562` if that substring is in `stdout+stderr`, raise `_AbortError(Rc.NOT_RUN)` BEFORE the topology check, so an unknown command is "never asked" rather than "expected output not written".

**Does it close the P1 it claims to?** Yes on the mechanism: the flag is explicit, and the rc-0-with-`Unknown command` case is routed to NOT_RUN ahead of the FINDINGS verdict. (Whether the literal `"Unknown command"` is what the binary actually prints is armed live below.)

**Does any test fail if you revert it? NO.** Measured on a scratch COPY of the tree (import path verified to be the scratch copy, not the editable install):

| module | tests | result |
|---|---|---|
| `c1d8afb8` (current, with fix) | current 26 | 26 passed, rc 0 |
| `c33a1fb5^` (pre-fix) | current 26 | **26 passed, rc 0** |

Both halves are invisible to the suite: `generate_declarations` is monkeypatched in every end-to-end test (`tests/test_mod_runtime.py:355`), so nothing observes its `env`; and the stub's `CompletedProcess` hardcodes `stdout="stub stdout"` (`:353`) with no way to inject `Unknown command`, so the new branch at `:551` is never taken. The fix is UNARMED, exactly as `c33a1fb5`'s own message says. The proposed arm tests and their two-way run follow in part 2.

## P1-3 — the live command writes into the caller's real HOME: REAL (the JSONL half, verified 13×); the `.claude.json` half is FIRST-RUN ONLY and was NOT observed in the real HOME

**Decides it.** `mod_runtime.py:425` `env = {**os.environ, "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}` — `HOME` (and `CLAUDE_CONFIG_DIR`, if a caller sets it) is inherited; only the cwd is isolated (`:528-529`).

**Measured in the REAL HOME, before any run of mine:** 13 directories `~/.claude/projects/-private-var-folders-…-T-kb-mod-runtime-<random>/`, mtimes **09:09 → 13:16 today**, each holding one `<uuid>.jsonl` (4,358 B in the one inspected) plus an empty `memory/`. `~/.claude/projects` has 81 entries; 13 are this gate's. The real `~/.claude.json` (170,548 B, has a `projects` key) contains **0** mentions of `kb-mod-runtime`; no other traces under `~/.claude` to depth 3.

**Measured under an ISOLATED HOME** (native 2.1.269, this session): every run — including the flag-off run that generated nothing — writes `~/.claude.json` (423–576 B: firstStartTime, machineID, userID, migration flags, `pluginUsage`; no `projects` key), `~/.claude/backups/.claude.json.backup.<ts>` (84 B), and `~/.claude/projects/<cwd-slug>/<uuid>.jsonl` (1,536 B / 3,339 B). So "settings, backups, JSONL" is what a FRESH home receives; a populated real home receives the project dir + JSONL only. The brief's "a `.claude.json`" is PARTIALLY REAL: first-run creation, not a per-run write.

**Failure scenario.** Not a race — unbounded accumulation: one never-cleaned project directory under a random name, plus a transcript, in the user's real profile, per gate run, forever. (Concurrent runs each get their own random dir, so the concurrency half of the audit's worry only bites on first-run `.claude.json` creation, which a populated home never hits.)

**Would a test catch it today? No.** `generate_declarations` is stubbed in every end-to-end test; nothing inspects `env`.

**Minimal fix** (prototyped and armed below): `HOME` → a sibling `home/` of a `work/` dir inside the same `TemporaryDirectory` — it must be BESIDE the work dir, because a HOME inside it would surface as `UNEXPECTED OUTPUT` in the topology check at `:564-565` — and `env.pop("CLAUDE_CONFIG_DIR", None)` so a caller override cannot route the writes back out. Live-armed this session: isolated HOME + flag → rc 0, both files, **9,156 / 10** lines — exactly the module's own "empty `HOME`" column at `:64-67`. Condition to carry: under an isolated HOME the primary file is the 24-built-in-tool variant, not 30; the module already states the 11 tokens are identical across both (`:73-75`) and reads only the primary file, so the verdict is unaffected and the docstring table then describes the environment the gate actually runs in.

## The fix `c33a1fb5` — part 2: live arms, proposed tests, two-way run

**Live** (native `~/.local/share/claude/versions/2.1.269`, isolated HOME, `stdin=DEVNULL`, the argv at `:427`):
- flag UNSET → rc **0**, output exactly `Unknown command: /plugin-types`, no files in cwd. The literal at `:143` matches what the binary prints, and rc 0 confirms `:535` cannot see this case.
- flag=1 → rc 0, `.claude/types/claude-code.d.ts` 9,156 lines + `claude-code-mcp.d.ts` 10 lines.

**Proposed tests** (`tests/test_fix_arms.py` in the prototype dir named below): (1) drive `check()` with `subprocess.run` spied and the flag DELETED from the test process's env; assert the spawned env carries `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`. The `delenv` is load-bearing — this session HAS the flag, so without it `{**os.environ}` inheritance would make the test tautological. (2) a generator stub that writes nothing, exits 0, prints `Unknown command: /plugin-types` → `check() == Rc.NOT_RUN`.

| module | (1) flag | (2) unknown→NOT_RUN |
|---|---|---|
| `c33a1fb5^` (pre-fix) | FAILED | FAILED |
| `c1d8afb8` (current) | passed | passed |
| `c1d8afb8` with `:551` severed to `if False:` | passed | **FAILED** — printed `EXPECTED OUTPUT NOT WRITTEN … claude-code.d.ts`, the exact misclassification the fix targets |

**Realistic arms for the committed spec** (`docs/research/arms/2026-09-12-g01-mod-runtime.toml`): A12 `old = 'if _UNKNOWN_COMMAND in combined:'` → `new = 'if False:'`, test (2). A13 `old = 'env = {**os.environ, "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}'` → `new = 'env = {**os.environ}'`, test (1). Both destroy what the check looks for; neither leaves the original as a substring.

**Verdict on the fix:** SOUND in mechanism and correctly targeted; **UNARMED as shipped** (revert → 26/26 green; no test in the tree can see either change). It neither touches nor claims to touch P1-1/2/3; P1-3's fix lands on the same line `:425`.

## NEW, outside the three: the gate is NOT_RUN on this machine RIGHT NOW, and `:373-378` is stale

`mise run kb-mod-runtime-check` → **rc 127**: *"`…/mise/installs/node/26.8.2/bin/claude --version` would not run — cannot probe the runtime"*. Second route: that path is a 3-line text wrapper → `../lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe`; its `package.json` says **2.1.270**; its platform optional dependency `@anthropic-ai/claude-code-darwin-arm64` is NOT installed (only `claude-code/` exists under `@anthropic-ai/`); direct `--version` → rc 1, "claude native binary not installed". `~/.local/share/claude/versions/{2.1.268,2.1.269,2.1.270}` all run. The 13 project dirs prove the gate DID run 09:09–13:16 today, so the wrapper broke after 13:16. `mise ls --installed` shows the mise npm-backend `claude-code` at 2.1.269 with no config source, while `mise which claude` resolves to a global-npm install inside node 26.8.2 (which `mise ls node` does not list). The docstring's "the shim and versions/2.1.269 both report 2.1.269" was true when written and is false now — the audit's item 7 "attribution race if the executable symlink moves" has happened.

Consequences: (a) `kb-gates`/`kb-ship` carry a 127 from this gate until the wrapper is repaired — NOT this module's defect, and the module classifies it correctly (NOT_RUN, never green); (b) `resolve_claude` is doing exactly what `:369-378` says. I did not investigate what upgraded the wrapper to 2.1.270 after 13:16 — out of scope.

## The three fixes, prototyped and armed (scratch copy, real tree untouched)

Prototype module `mod_runtime.PROPOSED.py` = current + P1-1b (bracket/destructure/template extraction), P1-2a (`_visible()` comment-stripping shared by `missing_tokens` and its control arm), P1-2b (dotted boundary), P1-3 (HOME beside work, `CLAUDE_CONFIG_DIR` dropped). Two test-file changes it forces, both visible: `tests/test_mod_runtime.py:252` fixture `"// {SYMBOL} leaked…"` → `"declare const _c: {SYMBOL};"` (under the new semantics a comment is not a leak), and `:346` `fake_generate` gains a third parameter. Under the prototype the committed contract is still exactly the 11.

| module | existing 26 (with the two fixture tweaks) | fix arms (2) | P1 arms (8) |
|---|---|---|---|
| `c33a1fb5^` | 26 passed | 2 failed | 7 failed / 1 passed |
| `c1d8afb8` | 26 passed | 2 passed | **7 failed / 1 passed** (only the exact-set pin passes — expected, it pins today's 11) |
| PROPOSED | 26 passed | 2 passed | 8 passed |
| PROPOSED, `:551` severed | — | 1 failed (2) | — |
| PROPOSED, `"HOME": str(home)` dropped | — | — | 1 failed (P1-3) |

Files (session scratchpad, shared with the lead's session): `/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/105dc66e-7e44-40e8-a094-72ea4b31a23f/scratchpad/repo/mod_runtime.PROPOSED.py`, `/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/105dc66e-7e44-40e8-a094-72ea4b31a23f/scratchpad/repo/tests/test_proposed_arms.py`, `/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/105dc66e-7e44-40e8-a094-72ea4b31a23f/scratchpad/repo/tests/test_fix_arms.py`, `/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/105dc66e-7e44-40e8-a094-72ea4b31a23f/scratchpad/repo/tests/test_mod_runtime_adjusted.py`, and a copy under `.agent/kb/review-round/lanes/a3-code-faults/`. The prototype diff:

```diff
--- mod_runtime.CURRENT.py	2026-09-12 15:25:21
+++ mod_runtime.PROPOSED.py	2026-09-12 15:30:28
@@ -178,6 +178,13 @@
 
 _IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*")
 
+#: `e["permissionMode"]` — run over the source WITH strings intact.
+_BRACKET_ACCESS = re.compile(r'\[\s*"([A-Za-z_$][\w$]*)"\s*\]')
+#: `const { a, b: alias } = e` — keys only, never the alias.
+_DESTRUCTURE = re.compile(r"(?:const|let|var)\s*\{([^}]*)\}\s*=")
+#: `${e.x}` bodies, pulled out of each template literal BEFORE it is blanked.
+_TEMPLATE_INTERP = re.compile(r"\$\{([^}]*)\}")
+
 #: Standard-library members that are properties of JS values rather than of the
 #: Claude Code runtime. Subtracted from the derived set.
 #:
@@ -307,6 +314,18 @@
     for matcher in _ON_MATCHER.findall(no_comments):
         tokens.update(_IDENTIFIER.findall(matcher))
     tokens.update(_OBJECT_KEY.findall(no_strings))
+    tokens.update(_BRACKET_ACCESS.findall(no_comments))
+    for group in _DESTRUCTURE.findall(no_strings):
+        for part in group.split(","):
+            key = re.split(r"[:=]", part, maxsplit=1)[0].strip()
+            if _IDENTIFIER.fullmatch(key) and key not in _JS_BUILTIN_MEMBERS:
+                tokens.add(key)
+    for literal in _TS_STRING.finditer(no_comments):
+        if literal.group().startswith("`"):
+            for body in _TEMPLATE_INTERP.findall(literal.group()):
+                tokens.update(
+                    p for p in _PROPERTY_ACCESS.findall(body) if p not in _JS_BUILTIN_MEMBERS
+                )
 
     if len(tokens) < _MINIMUM_REQUIRED_TOKENS or _REQUIRED_ANCHOR not in tokens:
         return None
@@ -330,14 +349,20 @@
     non-zero, stable) is identical under both, the digits are not.
     """
     if "." in token:
-        return re.compile(re.escape(token))
+        return re.compile(rf"(?<![\w$.]){re.escape(token)}(?![\w$])")
     return re.compile(rf"\b{re.escape(token)}\b")
 
 
+def _visible(declarations: str) -> str:
+    """The declarations minus comments: a symbol mentioned only in prose is not declared."""
+    return guard_inventory.strip_ts_comments(declarations)
+
+
 def missing_tokens(required: frozenset[str], declarations: str) -> frozenset[str]:
     """Which required tokens do NOT appear in the declarations at all."""
+    visible = _visible(declarations)
     return frozenset(
-        token for token in required if _token_pattern(token).search(declarations) is None
+        token for token in required if _token_pattern(token).search(visible) is None
     )
 
 
@@ -349,7 +374,7 @@
     ABSENT is what distinguishes "we looked and found them" from "we cannot
     look".
     """
-    return _token_pattern(_ABSENT_CONTROL_SYMBOL).search(declarations) is None
+    return _token_pattern(_ABSENT_CONTROL_SYMBOL).search(_visible(declarations)) is None
 
 
 def topology_findings(
@@ -399,7 +424,9 @@
     return proc.stdout.strip() or None
 
 
-def generate_declarations(binary: Path, workdir: Path) -> subprocess.CompletedProcess[str]:
+def generate_declarations(
+    binary: Path, workdir: Path, home: Path
+) -> subprocess.CompletedProcess[str]:
     """Run `/plugin-types` in `workdir`, which MUST NOT be the repo.
 
     🔴 **The fresh temp CWD is a correctness requirement, not tidiness.**
@@ -422,7 +449,8 @@
     of where it was run, which is the class `probes-need-a-control-arm.md` exists
     for.
     """
-    env = {**os.environ, "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}
+    env = {**os.environ, "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1", "HOME": str(home)}
+    env.pop("CLAUDE_CONFIG_DIR", None)  # a caller override would route the writes back out
     return subprocess.run(
         [str(binary), "-p", "/plugin-types", "--permission-mode", "bypassPermissions"],
         cwd=workdir,
@@ -526,9 +554,12 @@
     never touched.
     """
     with tempfile.TemporaryDirectory(prefix="kb-mod-runtime-") as tmp:
-        workdir = Path(tmp)
+        workdir = Path(tmp) / "work"
+        home = Path(tmp) / "home"
+        workdir.mkdir()
+        home.mkdir()
         try:
-            proc = generate_declarations(binary, workdir)
+            proc = generate_declarations(binary, workdir, home)
         except (OSError, subprocess.SubprocessError) as err:
             print(f"[mod-runtime-check] `/plugin-types` could not be run ({err}) — nothing probed")
             raise _AbortError(Rc.NOT_RUN) from err
```

Test-file changes the prototype forces:
```diff
--- tests/test_mod_runtime.py	2026-09-12 09:20:09
+++ tests/test_mod_runtime_adjusted.py	2026-09-12 15:30:28
@@ -249,7 +249,7 @@
     """The check's own control arm: a guaranteed-absent symbol must read ABSENT."""
     assert mod_runtime.matcher_can_report_absence("interface E { file_path: string; }")
     assert not mod_runtime.matcher_can_report_absence(
-        f"// {mod_runtime._ABSENT_CONTROL_SYMBOL} leaked into the declarations"
+        f"declare const _c: {mod_runtime._ABSENT_CONTROL_SYMBOL};"
     )
 
 
@@ -343,7 +343,9 @@
         monkeypatch.setattr(mod_runtime, "resolve_claude", lambda: Path("/stub/claude"))
         monkeypatch.setattr(mod_runtime, "claude_version", lambda _binary: "9.9.9 (stub)")
 
-        def fake_generate(_binary: Path, workdir: Path) -> subprocess.CompletedProcess[str]:
+        def fake_generate(
+            _binary: Path, workdir: Path, _home: Path | None = None
+        ) -> subprocess.CompletedProcess[str]:
             written = [p for p in mod_runtime.EXPECTED_OUTPUTS if p not in omit]
             for rel in [*written, *extra_outputs]:
                 target = workdir / rel
```

## Verdict

| item | verdict | minimal fix |
|---|---|---|
| P1-1 derived set under ordinary TS | **REAL** as a false claim at `:50-51` + latent gap (B/C/D invisible; G silent); NOT a wrong verdict on today's `register.ts` | pin the exact 11 in a test (loud); add bracket/destructure/template extraction or reword `:50-51` |
| P1-2 presence anywhere | **REAL**, disclosed `:86-97`, unmitigated; realistic "renamed, mentioned in a doc comment" case is green | strip comments in `missing_tokens` (+ control arm); dotted boundary; positional closure needs `tsc` (not pinned here — no `typescript` in `mise.toml`) |
| P1-3 real HOME writes | **REAL** (13 project dirs + JSONL, 09:09–13:16 today); `.claude.json` half PARTIALLY REAL (first-run only, 0 mentions in the real file) | `HOME` → sibling `home/` in the same tempdir; drop `CLAUDE_CONFIG_DIR`; live-armed rc 0 / 9,156 / 10 |
| fix `c33a1fb5` | **SOUND, UNARMED** — revert leaves 26/26 green | tests (1)+(2) above; arms A12/A13 |
| environment (new) | gate is **rc 127 NOT_RUN now** — PATH `claude` is a 2.1.270 npm wrapper without its native binary | not this module's; repair the wrapper before `kb-ship` |

## What I could not verify

- Whether the audit's "URL text can trigger the inherited non-lexical comment stripper and erase a following access" reproduces in SOME shape — my one shape (H) did not; I did not search for one that does.
- The exact write set in the REAL home per run beyond the project dir + JSONL — inferred from 13 historical runs plus the isolated-home write set; I did not run the gate against the real home myself (and could not: it is NOT_RUN now).
- What upgraded the global-npm `claude` to 2.1.270 after 13:16 and left its native dependency out.
- Whether an isolated HOME changes anything the primary d.ts token set depends on beyond what `:73-75` already measured — I re-derived nothing there; the 9,156/10 line counts matching the docstring's column is the only cross-check I ran.
- The prototype's `_DESTRUCTURE` and `_TEMPLATE_INTERP` on TypeScript the committed `register.ts` does not contain (nested braces in a destructure, a backtick inside `${}`) — untested; the 26 + 8 are the extent of the evidence.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review (`mod_runtime.py`, its tests, arms spec, `register.ts`, the vendored `.d.ts`, the audit reports); nothing external was consulted.
