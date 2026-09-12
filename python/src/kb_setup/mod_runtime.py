# Copyright (c) 2026 Raymond Manaloto
"""`kb-mod-runtime-check` — pin the function-hook runtime contract with LIVE probes (G01, #754).

This repo reasons about function hooks from
`sources/media/claude-code-function-hooks-types.d.ts`, vendored at Claude Code
**2.1.267**. Measured 2026-09-12, that file is **7,966** lines while the
installed 2.1.269 generates **9,263**, and it is missing an entire event
namespace the running binary carries (`session.authorize`: 0 vendored vs 7
generated). Nothing was detecting that. This module is the detector.

🔴 **INTENTIONALLY NON-HERMETIC, and that word is the one this ticket got
wrong.** The ticket asked for a check that was both "hermetic" and a live probe
of the installed runtime; those cannot both hold. What gives way is *hermetic*,
because it was never the real constraint — **credentials** were, and
`/plugin-types` needs none. Armed 2026-09-12, one variable (`HOME`), same
binary: with the real credentialed `$HOME` → rc 0, both files written; with
`HOME` pointed at a fresh empty temp dir → rc 0, both files written. No prompt,
no hang, no model call. So this check shells to `claude` and STILL runs on a
machine with no Claude credentials; what it genuinely needs is the binary, and
a machine without one gets :data:`Rc.NOT_RUN` (127), never a green.

That is also why this is in :data:`kb_setup.gates.GATE_TASKS` directly rather
than reached transitively through `pytest` the way `kb-guard-codegen-check` and
`kb-guard-inventory-check` are. Those two are hermetic and can be; this one
cannot, and the deciding risk is that a fixture-backed or vendored-file-backed
variant would go green **without ever examining the runtime it claims to
certify** — which is the precise failure this ticket exists to end. It runs
EXCLUSIVE (absent from :data:`~kb_setup.gates.CONCURRENT_SAFE`): it spawns a
subprocess whose contention with `test`'s xdist workers is uncharacterised, and
"we did not check" is not "it is safe".

## The three checks, and why each is shaped the way it is

1. **Output topology** (:func:`topology_findings`) — the generator must write
   EXACTLY :data:`EXPECTED_OUTPUTS`, no more and no fewer. Missing and extra are
   symmetric failures. This is deliberately **its own** detector and not
   `guard_codegen._stale_generated_files`: that one keys on a
   generated-provenance header we control, and these are third-party
   declarations in a directory we do not own, carrying no header of ours. What
   makes an exact-set test the right instrument here is a measurement — the file
   *contents* are environment-dependent (below) but both *filenames* appear in
   both arms, so the topology is invariant where the content is not.

2. **The consumer-required set** (:func:`required_runtime_tokens` ->
   :func:`missing_tokens`) — BLOCKING, and mechanically derived from
   `register.ts` rather than hand-authored. The deciding risk is specific: a
   hand-written contract encodes `agent_id` from the public docs while the
   function-hook event actually spells it **`agentId`**, and in that guard
   *absence is the ALLOW signal* — so a wrong contract fails open, silently,
   forever. A derived set cannot drift from its consumer that way.

   🔴 **"A new field joins the contract with no edit here" is TRUE ONLY FOR THE
   FORMS LISTED BELOW, and the unqualified claim that stood here until
   2026-09-12 was false.** Measured, one variant at a time, against the
   committed `register.ts`: dotted and optional-chained access grew the set,
   while `e["permissionMode"]`, `const { permissionMode } = e` and
   `` `${e.permissionMode}` `` inside a template literal each left it at 11 —
   invisible, with no test able to fail. All three are now extracted
   (:data:`_BRACKET_ACCESS`, :data:`_DESTRUCTURE`, :data:`_TEMPLATE_INTERP`),
   each with its own FAIL-direction arm in `tests/test_mod_runtime_arms.py`.

   What is still NOT extracted, stated so the next reader does not re-inherit an
   unqualified promise: computed access (`e[key]`), a spread into another object,
   and any field reached through a helper this module does not follow. The
   committed contract is therefore ALSO pinned by name in that test file, so a
   change to the derived set shows up as a diff a human reads rather than as a
   silently different set.

3. **The vendored delta** — INFORMATIONAL ONLY, never blocking. The vendored
   file keeps its bytes as immutable 2.1.267-labelled corpus evidence and is
   **retired as the runtime contract**. Positive cross-checks against it remain
   valid; negative ones never were.

## 🔴 Why no content hash of these files can ever be a gate

The generated declarations are **environment-dependent, not merely
version-dependent**. Armed twice independently on the same 2.1.269 binary with
`HOME` as the only variable:

| | real `HOME` | empty `HOME` |
|---|---|---|
| `claude-code.d.ts` | 9,263 lines | **9,156** |
| `claude-code-mcp.d.ts` | 2,588 lines | **10** |

The tool's own log says why — *"30 built-in tools / 170 MCP tools from 12
servers"* against *"24 built-in tools / no MCP tools connected"*. A whole-file
compare therefore reds on a **different machine at the same version**, which is
a stronger objection than the staleness one the ticket already raised. Every
one of the 11 tokens :func:`required_runtime_tokens` derives, by contrast, was
measured identical across both environments — which is exactly what makes check
2 machine-stable and check 1 the only safe use of the artifacts themselves.

Two consequences worth stating because they bound what this module claims:

- The token check reads **`claude-code.d.ts` only**. The MCP file collapses to
  10 lines under a bare `HOME`, so a token satisfied only there would be
  satisfied conditionally on the measuring machine's MCP inventory.
- The ticket's headline `+1,297 lines` is **confounded**: version-only is
  `+1,190` (7,966 -> 9,156) and the remaining `+107` is the measuring machine's
  own tool inventory. Nothing here depends on that figure.

## What this module does NOT prove

It reads text. A required token being *present* in the declarations is not
proof it is present in the right *position*, nor that the mod's hook would
actually fire. Of the 11 derived tokens, four (`tool.call`, `agentId`,
`file_path`, `deny`) are discriminating in practice and the rest are common
enough that their presence is close to guaranteed — they are carried anyway
because the derivation is mechanical, and a mechanical set that happens to
contain easy members is still a set that grows correctly when `register.ts`
does. Behavioural proof needs the mod REGISTERED and a real lane dispatched
against it, which is G04 (#757) and is the first point at which it is possible
at all. Residuals are filed, not hidden.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from kb_setup import guard_inventory
from kb_setup.result import Rc

#: The mod surface whose runtime dependencies are derived. Reused from
#: `guard_inventory` rather than re-spelled, so one rename moves both.
REGISTER_TS = guard_inventory.FUNCTION_HOOK_SOURCE_PATH

#: The 2.1.267 declarations, kept byte-pristine as corpus evidence. Read for the
#: INFORMATIONAL delta only — never as authority over a live probe.
VENDORED_DECLARATIONS = Path("sources/media/claude-code-function-hooks-types.d.ts")

#: Exactly what `/plugin-types` must write, relative to its working directory.
#: Measured 2026-09-12 on 2.1.269 under two different `HOME`s: both files appear
#: in both arms even though their CONTENTS differ, so this set is the
#: environment-invariant property of the generator.
#:
#: 🔴 **Stability across Claude Code VERSIONS is untested, and a new output file
#: will RED this gate.** That is the intended direction: a generator that starts
#: writing a third artifact has changed a contract this repo reads, and the
#: remedy is a human reviewing it and updating this tuple — not a check that
#: shrugs. Both arms behind this set ran 2.1.269.
EXPECTED_OUTPUTS = (
    Path(".claude/types/claude-code.d.ts"),
    Path(".claude/types/claude-code-mcp.d.ts"),
)

#: The declarations file the token contract is checked against. `claude-code-mcp.d.ts`
#: is deliberately NOT used: it is 2,588 lines on this machine and **10** under a
#: bare `HOME`, so a token satisfied only there is satisfied by local MCP
#: configuration rather than by the runtime contract.
PRIMARY_DECLARATIONS = Path(".claude/types/claude-code.d.ts")

#: Claude prints this and exits **0** when `/plugin-types` is not available —
#: so the rc cannot discriminate and this string is what does.
_UNKNOWN_COMMAND = "Unknown command"

#: Seconds. The measured generation is ~4s; this bounds a wedge rather than
#: predicting a duration (`.claude/rules/long-running-command-hangs.md`).
_GENERATE_TIMEOUT_S = 300

#: TypeScript string literals of all three kinds. Stripped BEFORE property
#: extraction, for the same reason `guard_inventory.strip_ts_comments` exists and
#: measured the same way: without this, prose inside `register.ts`'s own deny
#: message contributes `Report` and `Two` to the "property" set (from `. Report`
#: and `. Two`), and `".git"` contributes `git`. Four junk tokens out of 23 —
#: each of which would then be demanded of the declarations and red the gate.
_TS_STRING = re.compile(
    r'"(?:[^"\\\n]|\\.)*"'  # double-quoted
    r"|'(?:[^'\\\n]|\\.)*'"  # single-quoted
    r"|`(?:[^`\\]|\\.)*`"  # template literal
)

#: Any property access, dotted or optional-chained: `e.file_path`, `event?.agentId`.
#: Deliberately NOT anchored to a particular binding name. The event reaches
#: `laneOf` as a parameter named `event` and `handler` as one named `e`, so a
#: regex keyed on either identifier misses half the contract — including
#: `agentId`, the single field whose loss fails the guard OPEN.
_PROPERTY_ACCESS = re.compile(r"(?:\?\.|\.)\s*([A-Za-z_$][\w$]*)")

#: `on("<event>", ...)` — the event names this module registers for.
_ON_EVENT = re.compile(r'on\s*\(\s*"(?P<event>[^"]+)"')

#: `on("<event>", { <matcher> }, ...)` — the matcher keys.
_ON_MATCHER = re.compile(r'on\s*\(\s*"[^"]+"\s*,\s*\{(?P<matcher>[^}]*)\}')

#: Object-literal keys, which is how the hook's RETURN shape (`{ deny: ... }`)
#: enters the contract. Run over the string-stripped source so a colon inside
#: prose cannot contribute one.
_OBJECT_KEY = re.compile(r"(?m)^\s*(?P<key>[A-Za-z_$][\w$]*)\s*:")

_IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*")

#: `e["permissionMode"]` — run over the source WITH strings intact.
_BRACKET_ACCESS = re.compile(r'\[\s*"([A-Za-z_$][\w$]*)"\s*\]')
#: `const { a, b: alias } = e` — keys only, never the alias.
_DESTRUCTURE = re.compile(r"(?:const|let|var)\s*\{([^}]*)\}\s*=")
#: `${e.x}` bodies, pulled out of each template literal BEFORE it is blanked.
_TEMPLATE_INTERP = re.compile(r"\$\{([^}]*)\}")

#: Standard-library members that are properties of JS values rather than of the
#: Claude Code runtime. Subtracted from the derived set.
#:
#: 🔴 **This list's failure direction is CLOSED, which is what makes a
#: hand-maintained list acceptable here at all.** A builtin missing from it is
#: not subtracted, so it is demanded of the declarations and the gate REDS
#: loudly; it can never quietly shrink the contract. The opposite shape — a
#: hand-authored list of what the runtime *provides* — is the one the advisor
#: ruled against, because its failure direction is open.
_JS_BUILTIN_MEMBERS = frozenset(
    {
        "at",
        "charAt",
        "concat",
        "endsWith",
        "entries",
        "every",
        "filter",
        "find",
        "findIndex",
        "flat",
        "forEach",
        "includes",
        "indexOf",
        "isArray",
        "join",
        "keys",
        "lastIndexOf",
        "length",
        "map",
        "match",
        "padEnd",
        "padStart",
        "pop",
        "push",
        "reduce",
        "replace",
        "replaceAll",
        "reverse",
        "shift",
        "slice",
        "some",
        "sort",
        "split",
        "startsWith",
        "substring",
        "toLowerCase",
        "toString",
        "toUpperCase",
        "trim",
        "unshift",
        "values",
    }
)

#: The floor on the DISTINCT derived set (`guard_codegen._MINIMUM_PROTECTED_PATHS`'
#: precedent, and its caveat: a count is a weak invariant). It exists to catch
#: wholesale extractor breakage — a regex that stops matching returns a tidy,
#: internally consistent, nearly empty contract that every later check passes.
#: Today's derivation yields 11.
_MINIMUM_REQUIRED_TOKENS = 6

#: 🔴 The NAMED anchor, which is the strong half of the pair above. `agentId` is
#: the lane marker, it is spelled `agent_id` in the public docs and in classic
#: hooks, and in this guard **absence reads as ALLOW** — so losing it from the
#: derived set silently disarms the one check that cannot fail closed on its own.
#: A count cannot express that; this can.
#:
#: If the runtime itself ever renames the field, this gate REDS and a human
#: updates `register.ts` and this anchor together. That is the correct outcome,
#: and the reason a hand-named anchor is safe where a hand-named *contract* is
#: not: this one's failure direction is closed.
_REQUIRED_ANCHOR = "agentId"

#: A SYMBOL NAME guaranteed absent from any real declarations file. If the
#: matcher reports it PRESENT, the matcher is broken and every "present" verdict
#: beside it is worthless — so the run reports NOT_RUN rather than a green built
#: on an instrument that cannot produce a zero (`probes-need-a-control-arm.md`
#: rule 1, as a property of the check rather than of the session that wrote it).
#:
#: Named `..._SYMBOL` rather than `..._TOKEN` deliberately: ruff's `S105` flags
#: any constant whose name ends in `TOKEN` as a possible hardcoded credential.
#: The honest fix for a false positive is a name that is not misleading, never
#: an inline suppression (`zero-skip-policy.md`) — and "symbol" is in fact the
#: more accurate word for what this is: an identifier looked for in a
#: declarations file.
#:
#: (Writing that rule's marker out in full here is itself refused — `no_lint_skip`
#: is a SUBSTRING scan over `python/src/`, so a comment ABOUT a suppression reads
#: to it exactly like one. Caught by the gate on this very line.)
_ABSENT_CONTROL_SYMBOL = "ZZZ_kb_control_symbol_absent"


def strip_ts_strings(source: str) -> str:
    """Blank every string literal, preserving structure.

    Replaces each literal with `""` rather than deleting it, so a construct like
    `entry?.name === ".git"` keeps its shape and only its payload is removed.
    """
    return _TS_STRING.sub('""', source)


def required_runtime_tokens(register_source: str) -> frozenset[str] | None:
    """What `register.ts` requires OF THE RUNTIME, derived from its own text.

    Comments are stripped first (:func:`guard_inventory.strip_ts_comments`,
    public for exactly this reuse), then string literals
    (:func:`strip_ts_strings`). Both are load-bearing and were measured: the
    module's only literal `{ tool: "Edit" }` sits inside a doc comment, and its
    deny-message prose contributes four junk "properties" if strings survive.

    Returns `None` — which the caller reports as :data:`Rc.NOT_RUN`, never as a
    passing empty contract — when the derivation cannot be trusted: fewer than
    :data:`_MINIMUM_REQUIRED_TOKENS` distinct tokens, or a set that has lost
    :data:`_REQUIRED_ANCHOR`. An extractor that cannot see the current shape must
    say so, exactly as `guard_inventory.function_hook_write_tools` does.
    """
    no_comments = guard_inventory.strip_ts_comments(register_source)
    no_strings = strip_ts_strings(no_comments)

    tokens: set[str] = {
        prop for prop in _PROPERTY_ACCESS.findall(no_strings) if prop not in _JS_BUILTIN_MEMBERS
    }
    # Event names and matcher keys come from the source WITH strings intact —
    # the event name IS a string literal, so blanking it first would erase it.
    tokens.update(_ON_EVENT.findall(no_comments))
    for matcher in _ON_MATCHER.findall(no_comments):
        tokens.update(_IDENTIFIER.findall(matcher))
    tokens.update(_OBJECT_KEY.findall(no_strings))
    tokens.update(_BRACKET_ACCESS.findall(no_comments))
    for group in _DESTRUCTURE.findall(no_strings):
        for part in group.split(","):
            key = re.split(r"[:=]", part, maxsplit=1)[0].strip()
            if _IDENTIFIER.fullmatch(key) and key not in _JS_BUILTIN_MEMBERS:
                tokens.add(key)
    for literal in _TS_STRING.finditer(no_comments):
        if literal.group().startswith("`"):
            for body in _TEMPLATE_INTERP.findall(literal.group()):
                tokens.update(
                    p for p in _PROPERTY_ACCESS.findall(body) if p not in _JS_BUILTIN_MEMBERS
                )

    if len(tokens) < _MINIMUM_REQUIRED_TOKENS or _REQUIRED_ANCHOR not in tokens:
        return None
    return frozenset(tokens)


def _token_pattern(token: str) -> re.Pattern[str]:
    r"""Word-boundary match for an identifier; plain match for a dotted name.

    A dotted token such as `tool.call` is an event NAME appearing inside a string
    literal in the declarations, where `\\b` around the whole thing is both
    unnecessary and wrong at the dot.

    🔴 **The boundary is the load-bearing half, and it changes the answer.**
    `file_path` occurs **9** times in the vendored file by plain substring and
    **7** by word boundary; the two extras are longer field names that merely
    END in it. The question here is "does the runtime still carry a field called
    `file_path`", so the boundary form is the correct instrument and the plain
    count is a different measurement of a different thing. Stated because the
    design consult's evidence table used the plain form: the conclusion (present,
    non-zero, stable) is identical under both, the digits are not.
    """
    if "." in token:
        return re.compile(rf"(?<![\w$.]){re.escape(token)}(?![\w$])")
    return re.compile(rf"\b{re.escape(token)}\b")


def _visible(declarations: str) -> str:
    """The declarations minus comments: a symbol mentioned only in prose is not declared."""
    return guard_inventory.strip_ts_comments(declarations)


def missing_tokens(required: frozenset[str], declarations: str) -> frozenset[str]:
    """Which required tokens do NOT appear in the declarations at all."""
    visible = _visible(declarations)
    return frozenset(token for token in required if _token_pattern(token).search(visible) is None)


def matcher_can_report_absence(declarations: str) -> bool:
    """Can this matcher still produce a zero, per `probes-need-a-control-arm.md` rule 1?

    A matcher that reported everything present would pass :func:`missing_tokens`
    over an empty file. Asserting that a symbol which cannot be there reads as
    ABSENT is what distinguishes "we looked and found them" from "we cannot
    look".
    """
    return _token_pattern(_ABSENT_CONTROL_SYMBOL).search(_visible(declarations)) is None


def topology_findings(
    produced: set[Path], expected: set[Path]
) -> tuple[frozenset[Path], frozenset[Path]]:
    """Exact-set comparison over relative output paths: `(missing, extra)`.

    Symmetric by construction. An extra artifact is as much a contract change as
    a missing one, and native `datamodel-codegen --check` is measured to catch a
    deletion (rc 1, `MISSING:`) while missing a stale extra entirely (rc 0) —
    this check must not inherit that blind spot.
    """
    return frozenset(expected - produced), frozenset(produced - expected)


def resolve_claude() -> Path | None:
    """The `claude` a user of this machine would actually invoke, or `None`.

    `shutil.which` deliberately, rather than a versioned path under
    `~/.local/share/claude/versions/`: the point of this gate is the runtime
    that actually runs here. On this machine `which` resolves to a **mise
    shim**, and `.claude/rules/change-the-route.md` rule 6 is right that a shim
    is not "where the tool is" — but it IS what runs, and it was armed both
    ways: the shim and `~/.local/share/claude/versions/2.1.269` both report
    `2.1.269 (Claude Code)` and both generate identical output. The version is
    read from the binary rather than assumed for the same reason.
    """
    found = shutil.which("claude")
    return Path(found) if found else None


def claude_version(binary: Path) -> str | None:
    """`<binary> --version`, or `None` if it will not run."""
    try:
        proc = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=60,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def generate_declarations(
    binary: Path, workdir: Path, home: Path
) -> subprocess.CompletedProcess[str]:
    """Run `/plugin-types` in `workdir`, which MUST NOT be the repo.

    🔴 **The fresh temp CWD is a correctness requirement, not tidiness.**
    `/plugin-types` writes `.claude/types/*.d.ts` relative to its working
    directory, and `.claude/types/` in this repo is neither tracked nor
    gitignored — so a run in the repo root leaves two untracked files behind and
    dirties the tree. A gate that dirties the tree breaks `kb-gates`' own
    `dirty` accounting and `.claude/rules/clean-git-state.md` alike.

    `stdin` is `DEVNULL` because an inherited TTY is what turns a headless run
    into a hang.

    🔴 **`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` is set HERE, not inherited.** The
    `/plugin-types` command does not exist without it. This repo declares it in
    `.claude/settings.json`'s `env`, so a run from inside a Claude Code session
    inherits it and passes — while the same command in a plain terminal or CI
    silently gets a Claude that does not know the command. Armed 2026-09-12, same
    binary, flag the only variable: absent -> the gate reported FINDINGS "expected
    output not written"; present -> rc 0, clean. The gate was green only because
    of where it was run, which is the class `probes-need-a-control-arm.md` exists
    for.
    """
    # Annotated rather than inferred: `{**os.environ, …}` followed by a `pop`
    # with a `None` default widens the value type enough that no `subprocess.run`
    # overload matches, and ty says so at the CALL rather than here.
    env: dict[str, str] = {
        **os.environ,
        "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1",
        "HOME": str(home),
    }
    # A caller-set `CLAUDE_CONFIG_DIR` routes the writes back out of the isolated
    # HOME, which is the entire point of setting it.
    env.pop("CLAUDE_CONFIG_DIR", None)
    return subprocess.run(
        [str(binary), "-p", "/plugin-types", "--permission-mode", "bypassPermissions"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
        timeout=_GENERATE_TIMEOUT_S,
    )


def _report_vendored_delta(repo_root: Path, fresh: str, required: frozenset[str]) -> None:
    """INFORMATIONAL ONLY. Never returns an `Rc`, never blocks.

    The vendored 2.1.267 file is retired as the runtime contract, so a
    disagreement with it is news rather than a failure. Printing it keeps the
    corpus honest about how far behind its evidence has drifted.
    """
    vendored_path = repo_root / VENDORED_DECLARATIONS
    try:
        vendored = vendored_path.read_text(encoding="utf-8")
    except OSError as err:
        print(f"[mod-runtime-check] (informational) cannot read {VENDORED_DECLARATIONS}: {err}")
        return
    stale = sorted(missing_tokens(required, vendored))
    print(
        f"[mod-runtime-check] (informational) vendored {VENDORED_DECLARATIONS.name}: "
        f"{len(vendored.splitlines())} lines vs {len(fresh.splitlines())} generated"
    )
    if stale:
        print(
            "[mod-runtime-check] (informational) required tokens ABSENT from the vendored "
            f"file, present in the live one: {', '.join(stale)} — corpus evidence only, "
            "not a contract; this does not fail the gate"
        )


class _AbortError(Exception):
    """Internal control flow: a step that has decided the whole run's `Rc`.

    `result.py` draws the no-exceptions line at the COMMAND boundary — *"inside a
    module, ordinary Python control flow is unchanged; this is not a ban on
    `raise` everywhere, it is a contract about what a command hands back."*
    :func:`check` converts every one of these back into an `Rc` before returning,
    so nothing escapes.

    It exists because the alternative shapes are worse. A chain of `Rc | None`
    predicates (`guard_codegen`'s) cannot carry the generated declarations text
    that later steps need, and threading a mutable holder through them to fix
    that would hide the short-circuit this makes explicit.
    """

    def __init__(self, rc: Rc) -> None:
        super().__init__(rc)
        self.rc = rc


def _derive_contract(repo_root: Path) -> frozenset[str]:
    """Step 1 — what `register.ts` requires of the runtime. Raises on refusal."""
    try:
        register_source = (repo_root / REGISTER_TS).read_text(encoding="utf-8")
    except OSError as err:
        print(f"[mod-runtime-check] cannot read {REGISTER_TS}: {err}")
        raise _AbortError(Rc.NOT_RUN) from err

    required = required_runtime_tokens(register_source)
    if required is None:
        print(
            f"[mod-runtime-check] {REGISTER_TS}'s runtime dependencies could not be "
            f"derived — fewer than {_MINIMUM_REQUIRED_TOKENS} distinct symbols, or "
            f"`{_REQUIRED_ANCHOR}` (the lane marker, whose absence fails the guard OPEN) "
            "is no longer among them. The extractor cannot see the module's current "
            "shape; it must say so rather than report an empty contract as satisfied"
        )
        raise _AbortError(Rc.NOT_RUN)
    return required


def _resolve_runtime() -> tuple[Path, str]:
    """Step 2 — the installed binary and the version it reports. Raises on refusal."""
    binary = resolve_claude()
    if binary is None:
        print(
            "[mod-runtime-check] no `claude` binary on PATH — the runtime contract "
            "cannot be probed. This is NOT a pass: the question was never asked"
        )
        raise _AbortError(Rc.NOT_RUN)
    version = claude_version(binary)
    if version is None:
        print(f"[mod-runtime-check] `{binary} --version` would not run — cannot probe the runtime")
        raise _AbortError(Rc.NOT_RUN)
    return binary, version


def _generate_into_temp(binary: Path, version: str) -> str:
    """Step 3 — generate live, check output TOPOLOGY, return the primary declarations.

    The whole live half lives inside one `TemporaryDirectory` context, so the
    generated artifacts are gone by the time this returns and the repo tree is
    never touched.
    """
    with tempfile.TemporaryDirectory(prefix="kb-mod-runtime-") as tmp:
        workdir = Path(tmp) / "work"
        home = Path(tmp) / "home"
        workdir.mkdir()
        home.mkdir()
        try:
            proc = generate_declarations(binary, workdir, home)
        except (OSError, subprocess.SubprocessError) as err:
            print(f"[mod-runtime-check] `/plugin-types` could not be run ({err}) — nothing probed")
            raise _AbortError(Rc.NOT_RUN) from err
        if proc.returncode != 0:
            print(
                f"[mod-runtime-check] `/plugin-types` exited {proc.returncode} at {version} "
                "— the runtime was not described, so nothing was checked:"
            )
            print(proc.stdout + proc.stderr)
            raise _AbortError(Rc.NOT_RUN)

        # 🔴 Claude exits **0** while printing `Unknown command: /plugin-types`
        # when the feature flag is off or the command is gone. A zero rc is
        # therefore NOT evidence the generator ran, and treating the resulting
        # empty directory as missing OUTPUT misclassifies "we never asked" as
        # "the contract regressed" — a red ship gate pointing at the wrong thing,
        # with no mention of the cause. `Rc.NOT_RUN` is this repo's third state
        # for exactly this, and the message names the flag.
        combined = proc.stdout + proc.stderr
        if _UNKNOWN_COMMAND in combined:
            print(
                f"[mod-runtime-check] `{binary}` does not know `/plugin-types` at {version} "
                f"(it printed {_UNKNOWN_COMMAND!r} and still exited 0). The runtime was "
                "never described, so nothing was checked"
            )
            print(
                "[mod-runtime-check] the usual cause is the function-hooks feature flag: "
                "this check sets CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 for its own subprocess, "
                "so seeing this means the installed Claude Code no longer ships the command"
            )
            raise _AbortError(Rc.NOT_RUN)

        produced = {p.relative_to(workdir) for p in workdir.rglob("*") if p.is_file()}
        missing_files, extra_files = topology_findings(produced, set(EXPECTED_OUTPUTS))
        if missing_files or extra_files:
            for path in sorted(missing_files):
                print(f"[mod-runtime-check] EXPECTED OUTPUT NOT WRITTEN at {version}: {path}")
            for path in sorted(extra_files):
                print(
                    f"[mod-runtime-check] UNEXPECTED OUTPUT written at {version}: {path} — "
                    "the generator's artifact set changed; review it and update EXPECTED_OUTPUTS"
                )
            raise _AbortError(Rc.FINDINGS)

        try:
            return (workdir / PRIMARY_DECLARATIONS).read_text(encoding="utf-8")
        except OSError as err:
            print(f"[mod-runtime-check] cannot read the generated {PRIMARY_DECLARATIONS}: {err}")
            raise _AbortError(Rc.NOT_RUN) from err


def _reconcile_contract(required: frozenset[str], fresh: str, version: str) -> None:
    """Step 4 — every required symbol must be declared by the live runtime."""
    if not matcher_can_report_absence(fresh):
        print(
            "[mod-runtime-check] the symbol matcher reports a guaranteed-absent control "
            "symbol as PRESENT — the instrument is broken, so every 'present' verdict "
            "beside it is worthless. Reporting NOT_RUN rather than a green"
        )
        raise _AbortError(Rc.NOT_RUN)

    absent = sorted(missing_tokens(required, fresh))
    if absent:
        print(
            f"[mod-runtime-check] {REGISTER_TS} depends on {len(absent)} symbol(s) the "
            f"installed Claude Code {version} no longer declares: {', '.join(absent)}"
        )
        print(
            "[mod-runtime-check] a field the guard reads but the runtime does not send "
            "is `undefined` at runtime, and in this guard absence is the ALLOW signal — "
            "so this is a silent fail-OPEN, not a type error"
        )
        raise _AbortError(Rc.FINDINGS)


def check(repo_root: Path) -> Rc:
    """The gate. Generates live, then reconciles topology and the consumer set.

    Four steps, each its own function above, each raising :class:`_AbortError` with
    the verdict it has decided. Converting that back to an `Rc` here is the only
    place a verdict leaves this module.
    """
    required: frozenset[str] | None = None
    fresh: str | None = None
    try:
        required = _derive_contract(repo_root)
        binary, version = _resolve_runtime()
        fresh = _generate_into_temp(binary, version)
        _reconcile_contract(required, fresh, version)
    except _AbortError as abort:
        # The informational delta still runs when the FINDING is about the
        # contract itself — that is exactly when "how far has the vendored
        # evidence drifted" is worth printing. It cannot run before the live
        # declarations exist.
        if required is not None and fresh is not None:
            _report_vendored_delta(repo_root, fresh, required)
        return abort.rc

    print(
        f"[mod-runtime-check] clean: generated the declarations live at {version}, which "
        f"wrote exactly the {len(EXPECTED_OUTPUTS)} expected artifacts, and all "
        f"{len(required)} symbols mechanically derived from {REGISTER_TS.name} are declared "
        f"by that runtime. NOT proven here: that those symbols appear in the right "
        f"POSITION, or that the mod's hook fires at all — this reads declarations, it does "
        f"not run the guard (see #757)."
    )
    _report_vendored_delta(repo_root, fresh, required)
    return Rc.OK


#: The committed arms spec `--arms` proves this module against. Named here rather
#: than passed in, because `--arms` is a fixed proving mode of THIS check, not a
#: general runner: `mise run kb-arms -- <spec>` is the general one.
ARMS_SPEC = Path("docs/research/arms/2026-09-12-g01-mod-runtime.toml")


def main(repo_root: Path, argv: list[str]) -> int:
    """`kb-setup mod-runtime-check [--arms [--dry-run]]`.

    The bare form is the gate. `--arms` is the PROVING mode and is deliberately
    not what enters `GATE_TASKS`: `kb_setup.arms` mutates tracked files while it
    runs, which no gate may do.
    """
    if "--arms" in argv:
        from kb_setup import arms

        rest = [a for a in argv if a != "--arms"]
        return arms.main([str(ARMS_SPEC), *rest], repo_root)
    if argv:
        print(f"[mod-runtime-check] unknown argument(s): {' '.join(argv)}")
        return int(Rc.BAD_REQUEST)
    return int(check(repo_root))
