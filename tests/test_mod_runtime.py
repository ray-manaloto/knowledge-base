# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.mod_runtime` — G01 (#754), the function-hook runtime contract.

🔴 **Every test here is HERMETIC and none of them needs the `claude` binary**,
which is what lets them run inside `test` (a `CONCURRENT_SAFE` gate) while the
module they cover is deliberately non-hermetic and runs EXCLUSIVE in
`GATE_TASKS`. The split is the point: the live half proves the runtime is what
we think it is, and this half proves the DETECTION LOGIC would notice if it
were not.

That split is also what makes this module armable at all. `kb_setup.arms` shells
`python -m pytest` and nothing else (`arms.py:289-306`), so an arm's mutation is
only ever caught by a named pytest — a check reachable only through a live
subprocess has no arm. The committed spec is
`docs/research/arms/2026-09-12-g01-mod-runtime.toml`.

The control arm (`test_the_committed_register_ts_derives_a_usable_contract`)
reads the REAL `register.ts`; everything else is synthetic source text, so no
test here mutates anything on disk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

import pytest
from kb_setup import mod_runtime
from kb_setup.result import Rc

REPO = Path(__file__).resolve().parents[1]


class _StubRuntime(Protocol):
    """The `stub_runtime` fixture's callable, typed so no annotation is silenced."""

    def __call__(
        self,
        declarations: str,
        *,
        extra_outputs: tuple[Path, ...] = (),
        omit: tuple[Path, ...] = (),
        returncode: int = 0,
    ) -> None: ...


#: A minimal `register.ts` carrying every shape the extractor must see: a doc
#: comment holding a literal that must NOT count, a string literal holding prose
#: that must NOT count, the event name (which IS a string and must count), a
#: shorthand matcher, an optional-chained event field on a binding named
#: something other than `e`, a plain event field, a `$` chain, and the deny shape.
_SYNTHETIC_REGISTER = """
/**
 * A doc comment mentioning { tool: "Edit" } which must not enter the contract,
 * and describing a REJECTED earlier design that read $.session.cwd() — the real
 * case register.ts carries, and the one a raw-text scan wrongly picks up.
 */
export function laneOf(event: { agentId?: unknown }): string | null {
  const id = event?.agentId;
  return typeof id === "string" ? id : null;
}

async function handler($: any, e: any, next: any): Promise<any> {
  const entries = await $.fs.list("/some/dir");
  const dotGit = entries.find((entry: any) => entry?.name === ".git");
  if (!dotGit || dotGit.kind !== "file") {
    $.ui.log("denied " + e.tool + " on " + e.file_path);
    return {
      deny: "Refused. Report this rather than retrying.",
    };
  }
  return next(e);
}

export function register(on: any): void {
  for (const tool of WRITE_TOOLS) {
    on("tool.call", { tool }, handler);
  }
}
"""


# --------------------------------------------------------------------------
# Control arm — runs against the real tree.
# --------------------------------------------------------------------------


def test_the_committed_register_ts_derives_a_usable_contract() -> None:
    """THE CONTROL. If this fails, every FAIL-direction test below is void."""
    source = (REPO / mod_runtime.REGISTER_TS).read_text(encoding="utf-8")
    required = mod_runtime.required_runtime_tokens(source)
    assert required is not None, "the committed register.ts must yield a derivable contract"
    # The four symbols with real discriminating power, named rather than counted.
    assert {"tool.call", "agentId", "file_path", "deny"} <= required
    assert len(required) >= mod_runtime._MINIMUM_REQUIRED_TOKENS


def test_the_matcher_finds_real_symbols_in_the_vendored_declarations() -> None:
    """A POSITIVE cross-check against the vendored file — a HISTORICAL pair.

    The vendored 2.1.267 declarations are retired as *negative* authority — an
    absence there proves nothing about the runtime. A presence still proves
    presence, and this is the cheap hermetic arm that the required-token matcher
    finds real symbols in a real declarations file rather than matching nothing.

    🔴 **It is pinned to a FIXED historical set, not to today's derived one, and
    that distinction was a real defect.** This assertion used to compare the live
    `required_runtime_tokens(register.ts)` against the 2.1.267 file, which made
    absence from an immutable historical snapshot BLOCKING for a growing
    consumer. Measured by a cold lane: adding a `session.authorize` registration
    to a copy of `register.ts` turned this test from exit 0 to exit 1, while
    reconciliation against declarations that actually carry that event exited 0.
    So adopting any newer runtime capability would red pytest while the live
    contract passed — the module's own "retired as negative authority" stance,
    contradicted by its own test.

    Pairing a historical declarations file with a historical token set keeps the
    property that is actually worth asserting (the matcher is not vacuously
    matching nothing) and drops the one that was never true.
    """
    historical = frozenset({"tool.call", "agentId", "file_path", "deny"})
    vendored = (REPO / mod_runtime.VENDORED_DECLARATIONS).read_text(encoding="utf-8")
    assert mod_runtime.missing_tokens(historical, vendored) == frozenset()
    # The control: the same matcher against the same file MUST be able to report
    # absence, or the assertion above is satisfied by a matcher that says yes to
    # everything.
    assert mod_runtime.missing_tokens(frozenset({"kbAbsentControlSymbol"}), vendored) == frozenset(
        {"kbAbsentControlSymbol"}
    )


# --------------------------------------------------------------------------
# Extraction — what enters the contract, and what must not.
# --------------------------------------------------------------------------


def test_a_literal_inside_a_comment_does_not_enter_the_contract() -> None:
    """`{ tool: "Edit" }` sits in a DOC COMMENT in the real module.

    Without comment stripping the extractor reads `Edit` as an object key and
    demands the declarations contain it as a runtime symbol.
    """
    required = mod_runtime.required_runtime_tokens(_SYNTHETIC_REGISTER)
    assert required is not None
    assert "Edit" not in required
    # 🔴 The discriminating pair. `Edit` alone does NOT prove comment stripping:
    # it sits inside a string AND off a line start, so the string blanker and the
    # object-key anchor each independently exclude it — measured, when severing
    # `strip_ts_comments` left this test green and reddened a different one.
    # `session`/`cwd` come from a property access in a comment, which nothing
    # else removes.
    assert "session" not in required
    assert "cwd" not in required


def test_prose_inside_a_string_does_not_enter_the_contract() -> None:
    """Measured on the real module: four junk tokens of 23 come from strings.

    `". Report this"` yields `Report` and `".git"` yields `git` through the
    property-access regex, because a full stop followed by a word is
    indistinguishable from a member access once you are only matching text.
    Each junk token would then be demanded of the declarations.
    """
    required = mod_runtime.required_runtime_tokens(_SYNTHETIC_REGISTER)
    assert required is not None
    assert "Report" not in required
    assert "git" not in required


def test_the_registered_event_name_is_part_of_the_contract() -> None:
    """The registered event name is part of the contract.

    `tool.call` is a STRING literal, so it survives only because the event
    extraction runs before string blanking. Losing it loses the one token that
    says which event this module is even registered for.
    """
    required = mod_runtime.required_runtime_tokens(_SYNTHETIC_REGISTER)
    assert required is not None
    assert "tool.call" in required


def test_an_event_field_read_off_a_binding_not_named_e_is_still_found() -> None:
    """🔴 `agentId` is read as `event?.agentId` inside `laneOf`, not `e.agentId`.

    An extractor keyed on the handler's own parameter name misses exactly the
    field whose loss fails this guard OPEN.
    """
    required = mod_runtime.required_runtime_tokens(_SYNTHETIC_REGISTER)
    assert required is not None
    assert "agentId" in required


def test_javascript_builtins_are_not_demanded_of_the_runtime() -> None:
    """`.find(...)` is `Array.prototype.find`, not a Claude Code symbol."""
    required = mod_runtime.required_runtime_tokens(_SYNTHETIC_REGISTER)
    assert required is not None
    assert "find" not in required


# --------------------------------------------------------------------------
# The two ways a derived contract must refuse rather than pass.
# --------------------------------------------------------------------------


def test_a_renamed_lane_marker_makes_the_contract_underivable() -> None:
    """🔴 THE SPELLING TRAP, as a refusal.

    A module reading `agent_id` (the docs' and classic hooks' spelling) instead
    of `agentId` gets `undefined` on every call and allows everything. The
    extractor must not hand back a tidy contract that happens to omit the one
    symbol whose absence cannot fail closed.
    """
    renamed = _SYNTHETIC_REGISTER.replace("agentId", "agent_id")
    assert mod_runtime.required_runtime_tokens(renamed) is None


def test_a_collapsed_extractor_result_is_not_a_passing_contract() -> None:
    """A source the extractor cannot read yields `None`, never an empty set.

    An empty contract is satisfied by every declarations file ever written,
    including an empty one — the shape of a gate reporting clean without
    checking anything.
    """
    assert mod_runtime.required_runtime_tokens("") is None
    assert mod_runtime.required_runtime_tokens("export function register(on) {}") is None
    # 🔴 The case that isolates the FLOOR from the anchor beside it. Both of the
    # sources above are also refused by the `agentId` anchor, so neither can tell
    # the two clauses apart — measured, when severing the floor alone left this
    # test green. This source satisfies the anchor and is still far too small to
    # be a real contract.
    assert mod_runtime.required_runtime_tokens("const id = event?.agentId;") is None


# --------------------------------------------------------------------------
# Reconciliation against the declarations.
# --------------------------------------------------------------------------


def test_a_symbol_the_runtime_stopped_declaring_is_reported() -> None:
    required = frozenset({"agentId", "file_path"})
    declarations = "interface ToolCallEvent { file_path: string; }"
    assert mod_runtime.missing_tokens(required, declarations) == frozenset({"agentId"})


def test_a_longer_field_that_merely_ends_in_a_required_name_is_not_a_match() -> None:
    """🔴 Word boundaries change the answer, measured on the real vendored file.

    `file_path` occurs 9 times there by plain substring and 7 by word boundary;
    the extras are longer field names ending in it. A substring matcher reports
    the contract satisfied by a field that is not the field.
    """
    declarations = "interface E { notebook_file_path: string; }"
    assert mod_runtime.missing_tokens(frozenset({"file_path"}), declarations) == frozenset(
        {"file_path"}
    )


def test_a_dotted_event_name_is_matched_whole() -> None:
    r"""`tool.call` is matched plainly — `\\b` around a dotted name is wrong at the dot."""
    assert mod_runtime.missing_tokens(frozenset({"tool.call"}), 'on("tool.call")') == frozenset()
    assert mod_runtime.missing_tokens(frozenset({"tool.call"}), 'on("tool.result")') == frozenset(
        {"tool.call"}
    )


def test_a_matcher_that_reports_everything_present_is_caught() -> None:
    """The check's own control arm: a guaranteed-absent symbol must read ABSENT."""
    assert mod_runtime.matcher_can_report_absence("interface E { file_path: string; }")
    assert not mod_runtime.matcher_can_report_absence(
        f"declare const _c: {mod_runtime._ABSENT_CONTROL_SYMBOL};"
    )


# --------------------------------------------------------------------------
# Output topology — the two states the ticket's literal Arm action wanted,
# constructed here instead (verdict D).
# --------------------------------------------------------------------------


def test_a_missing_expected_output_is_caught() -> None:
    produced = {mod_runtime.EXPECTED_OUTPUTS[0]}
    missing, extra = mod_runtime.topology_findings(produced, set(mod_runtime.EXPECTED_OUTPUTS))
    assert missing == frozenset({mod_runtime.EXPECTED_OUTPUTS[1]})
    assert extra == frozenset()


def test_a_stale_extra_output_is_caught() -> None:
    """The half native `datamodel-codegen --check` provably MISSES.

    Measured for G02: a planted orphan beside the real artifacts returns rc 0
    from the native checker. An exact-set test is symmetric by construction and
    cannot inherit that blind spot.
    """
    orphan = Path(".claude/types/claude-code-legacy.d.ts")
    produced = {*mod_runtime.EXPECTED_OUTPUTS, orphan}
    missing, extra = mod_runtime.topology_findings(produced, set(mod_runtime.EXPECTED_OUTPUTS))
    assert missing == frozenset()
    assert extra == frozenset({orphan})


def test_the_expected_topology_reconciles_clean() -> None:
    missing, extra = mod_runtime.topology_findings(
        set(mod_runtime.EXPECTED_OUTPUTS), set(mod_runtime.EXPECTED_OUTPUTS)
    )
    assert (missing, extra) == (frozenset(), frozenset())


# --------------------------------------------------------------------------
# "Could not ask" is never a pass.
# --------------------------------------------------------------------------


def test_no_claude_binary_reports_not_run_rather_than_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🔴 The whole reason this gate is allowed to be non-hermetic.

    A machine with no `claude` must report that the question was never asked.
    Collapsing that into OK is how a gate certifies a runtime it never examined.
    """
    monkeypatch.setattr(mod_runtime, "resolve_claude", lambda: None)
    assert mod_runtime.check(REPO) == Rc.NOT_RUN


def test_an_unreadable_register_ts_reports_not_run(tmp_path: Path) -> None:
    assert mod_runtime.check(tmp_path) == Rc.NOT_RUN


def test_an_unknown_argument_is_a_bad_request() -> None:
    assert mod_runtime.main(REPO, ["--nonsense"]) == int(Rc.BAD_REQUEST)


# --------------------------------------------------------------------------
# `check()` end to end, with ONLY the live half stubbed.
#
# 🔴 These exist because a mutation sweep found the gap they close. Three arms
# SURVIVED against the first version of this file — severing the topology
# verdict, the matcher's own control arm, and the missing-binary branch — all
# for one reason: every test above exercises a PREDICATE, and none of them
# exercised its CALL SITE. `guard_codegen`'s docstring names exactly this defeat
# ("deleting its CALL SITE so a perfectly correct predicate is invoked by
# nobody"); it was written down and repeated anyway.
#
# Stubbing `resolve_claude`/`claude_version`/`generate_declarations` — and
# nothing else — keeps these hermetic while running the real orchestration,
# the real topology comparison and the real reconciliation.
# --------------------------------------------------------------------------


@pytest.fixture
def stub_runtime(monkeypatch: pytest.MonkeyPatch) -> _StubRuntime:
    """Install a fake `claude` that writes exactly what the test asks for."""

    def install(
        declarations: str,
        *,
        extra_outputs: tuple[Path, ...] = (),
        omit: tuple[Path, ...] = (),
        returncode: int = 0,
    ) -> None:
        monkeypatch.setattr(mod_runtime, "resolve_claude", lambda: Path("/stub/claude"))
        monkeypatch.setattr(mod_runtime, "claude_version", lambda _binary: "9.9.9 (stub)")

        def fake_generate(
            _binary: Path, workdir: Path, _home: Path | None = None
        ) -> subprocess.CompletedProcess[str]:
            written = [p for p in mod_runtime.EXPECTED_OUTPUTS if p not in omit]
            for rel in [*written, *extra_outputs]:
                target = workdir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                body = declarations if rel == mod_runtime.PRIMARY_DECLARATIONS else "// stub\n"
                target.write_text(body, encoding="utf-8")
            return subprocess.CompletedProcess([], returncode, "stub stdout", "")

        monkeypatch.setattr(mod_runtime, "generate_declarations", fake_generate)

    return install


#: Declarations a real `register.ts` contract is satisfied by — every symbol the
#: committed module derives, in one line each.
def _satisfying_declarations() -> str:
    source = (REPO / mod_runtime.REGISTER_TS).read_text(encoding="utf-8")
    required = mod_runtime.required_runtime_tokens(source)
    assert required is not None
    return "\n".join(f"declare const _{i}: {tok};" for i, tok in enumerate(sorted(required)))


def test_check_is_clean_when_the_live_runtime_declares_everything(
    stub_runtime: _StubRuntime,
) -> None:
    """The positive control for the three FAIL-direction tests below."""
    stub_runtime(_satisfying_declarations())
    assert mod_runtime.check(REPO) == Rc.OK


def test_check_reports_findings_when_the_generator_writes_an_extra_artifact(
    stub_runtime: _StubRuntime,
) -> None:
    """A1's gap: the topology VERDICT, not just `topology_findings` in isolation."""
    stub_runtime(
        _satisfying_declarations(),
        extra_outputs=(Path(".claude/types/claude-code-legacy.d.ts"),),
    )
    assert mod_runtime.check(REPO) == Rc.FINDINGS


def test_check_reports_findings_when_an_expected_artifact_is_missing(
    stub_runtime: _StubRuntime,
) -> None:
    """The other direction of the same verdict, constructed rather than deleted."""
    stub_runtime(_satisfying_declarations(), omit=(mod_runtime.EXPECTED_OUTPUTS[1],))
    assert mod_runtime.check(REPO) == Rc.FINDINGS


def test_check_reports_findings_when_the_runtime_drops_a_required_symbol(
    stub_runtime: _StubRuntime,
) -> None:
    """🔴 The spelling trap as the gate sees it: `agentId` gone from the runtime."""
    satisfying = _satisfying_declarations()
    stub_runtime(satisfying.replace("agentId", "agent_id"))
    assert mod_runtime.check(REPO) == Rc.FINDINGS


def test_check_reports_not_run_when_its_own_matcher_is_broken(stub_runtime: _StubRuntime) -> None:
    """A8's gap: the control arm's CALL SITE inside `check`, not the predicate."""
    control = mod_runtime._ABSENT_CONTROL_SYMBOL
    stub_runtime(_satisfying_declarations() + f"\ndeclare const _c: {control};\n")
    assert mod_runtime.check(REPO) == Rc.NOT_RUN


def test_check_reports_not_run_when_the_generator_fails(stub_runtime: _StubRuntime) -> None:
    stub_runtime(_satisfying_declarations(), returncode=2)
    assert mod_runtime.check(REPO) == Rc.NOT_RUN


def test_no_binary_short_circuits_before_trying_to_execute_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A10's gap: `check` returns NOT_RUN either way, so the Rc cannot discriminate.

    🔴 What the arm actually severs is the SHORT-CIRCUIT. Without it, `check`
    falls through to `claude_version(None)`, which stringifies `None` and hands
    `"None"` to `subprocess.run` as a program name — an attempt to execute a
    binary whose name came from a failed lookup. It happens to raise `OSError`
    and end at the same `Rc.NOT_RUN`, which is exactly why asserting on the Rc
    could not see the mutation. Asserting that the second probe is never reached
    can.
    """
    called: list[Path] = []

    def spy(binary: Path) -> str | None:
        called.append(binary)
        return None

    monkeypatch.setattr(mod_runtime, "resolve_claude", lambda: None)
    monkeypatch.setattr(mod_runtime, "claude_version", spy)
    assert mod_runtime.check(REPO) == Rc.NOT_RUN
    assert called == [], "a missing binary must not be handed to subprocess as a program name"
