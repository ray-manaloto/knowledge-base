# Copyright (c) 2026 Raymond Manaloto
"""Fail-closed real-Claude semantic slice for the pinned Graphify source."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import warnings
from collections.abc import Generator, Mapping, MutableMapping
from contextlib import contextmanager, redirect_stderr
from pathlib import Path

import msgspec

from kb_setup import events, graphify_baseline
from kb_setup.graphify_baseline import RuntimeIdentity

_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
_CLAUDE_CANONICAL_MODEL = "claude-haiku-4-5"
_CLAUDE_PROVIDER = "firstParty"
_MAX_TURNS_WITH_ONE_STRUCTURED_REPAIR = 3
_MAX_COST_USD = 0.25
CLAUDE_MODEL = _CLAUDE_MODEL
# Name of the ONE environment variable that selects a profile at the adapter
# boundary. Its VALUE is allowlisted to the two reviewed profile names below —
# never a model string, never a budget. A boundary whose model and spend cap can
# be set to anything by an environment variable is not a fail-closed boundary,
# so the env carries a choice between reviewed shapes and nothing else.
PROFILE_ENV_NAME = "KB_SEMANTIC_PROFILE"
GRAPHIFY_SCHEMA_SHA256 = "69d307d23913e0cccf5809316a3432b85210776bd5626a4ad0af1317d6113324"

# Only the SNAPSHOT identity moves v0.9.45 -> v0.9.48 (2026-08-21 re-attest). The
# file itself is BYTE-IDENTICAL across the two tags — same blob, same size, same
# digest, so `SOURCE_GIT_OBJECT`/`SOURCE_SHA256`/`SOURCE_SIZE` below do not move —
# and that is a measurement: `git -C sources/graphify rev-parse v0.9.48`,
# `rev-parse 'v0.9.48^{tree}'`, and `rev-parse v0.9.48:docs/how-it-works.md`
# against the pinned clone, not carried forward from the v0.9.45 round.
SOURCE_REF = "v0.9.48"
SOURCE_COMMIT = "b2cd36267456c166788c95be6e68574064a92a42"
SOURCE_TREE = "be8636735370ed82708bb53eba33170e85acc369"
SOURCE_PATH = "docs/how-it-works.md"
# UNCHANGED across v0.9.45 -> v0.9.48, so the slice's INPUT is byte-identical and
# the re-run only re-attests it under the new runtime. Measured by three routes
# that agree: the contents API at each of the two commits, and `git hash-object`
# on the local clone. `SOURCE_TREE` above moved in the same derivation, which is
# what shows these probes can return a different value rather than echoing back
# whatever they were asked about.
SOURCE_GIT_OBJECT = "e0e6e5275dfec50b25c38590f151ebd9e263f383"
SOURCE_SHA256 = "cd4a67001704eddc557d67eaa783d0608cd200302fa1b89c3f1a4819497cdc26"
SOURCE_SIZE = 5147
_CANDIDATE_SCHEMA = "graphify-real-semantic-slice/v0"
# ADVANCED alongside the graphify 0.9.48 re-attest (2026-08-21): the sha256 of
# the CANDIDATE manifest.json the re-run published, replacing the 0.9.45 value.
# Advanced only AFTER `build_candidate` published that evidence and `verify`
# was observed reporting `candidate-authority-mismatch` against the prior value.
_ACCEPTED_CANDIDATE_MANIFEST_SHA256 = (
    "61006e39d3d6ea20e1bb41deff64ff3cffbcf1894db92920a9006924c19f4cc9"
)
_MAX_SEMANTIC_ARGS = 2
_PROVIDER_BOUNDARY_MEMBER = "provider-boundary-start.json"
_REQUIRED_MEMBERS = frozenset(
    {
        "adapter-metadata.json",
        "receipt.json",
        "semantic-fragment.json",
        # Retained as a candidate member rather than written to a temp dir: a
        # boundary marker that is not kept is not evidence.
        _PROVIDER_BOUNDARY_MEMBER,
    }
)

_REQUIRED_CLAUDE_FLAGS = (
    "--json-schema",
    "--max-budget-usd",
    "--model",
    "--no-chrome",
    "--no-session-persistence",
    "--output-format",
    "--permission-mode",
    "--safe-mode",
    "--strict-mcp-config",
    "--tools",
)
_CHILD_CONTROL_ENV = {
    "API_TIMEOUT_MS": "120000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_DISABLE_TELEMETRY": "1",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "4096",
    "CLAUDE_CODE_MAX_RETRIES": "0",
    "MAX_STRUCTURED_OUTPUT_RETRIES": "1",
}
_CHILD_BASE_ENV_NAMES = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "USER",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
)

_ROUTE_OVERRIDE_NAMES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_SMALL_FAST_MODEL",
        "ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION",
        "ANTHROPIC_VERTEX_BASE_URL",
        "CLAUDE_CODE_SKIP_BEDROCK_AUTH",
        "CLAUDE_CODE_SKIP_VERTEX_AUTH",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_SUBAGENT_MODEL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
        "CLAUDE_CODE_USE_VERTEX",
        "ANTHROPIC_VERTEX_PROJECT_ID",
        "CLOUD_ML_REGION",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_API_KEY",
        "ANTHROPIC_CUSTOM_HEADERS",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    }
)

# EXCLUDED from `scrub_route_overrides` (cold review P2-4) — `preflight`'s
# refusal still fires on all four, unchanged, because they stay IN
# `_ROUTE_OVERRIDE_NAMES` above; only the scrub leaves them alone. Egress
# configuration is not a routing credential, and scrubbing it from THIS
# process is not the same decision as scrubbing it from the `claude` CHILD.
# `claude_child_environment` (below) builds a closed allowlist that never
# copies a proxy name regardless of what this process's own `os.environ`
# carries, so the child was always proxy-free downstream of `preflight` — that
# is the true scope of "the child environment already did this", and it does
# not extend to the parent. The parent-scope consumers a scrub WOULD touch are
# `git` (`_admit_source` -> `graph.materialize_source_snapshot`) and the
# in-process graphify SDK, whose httpx client defaults to `trust_env=True`. On
# a host actually behind a proxy, deleting these four turns `preflight`'s loud
# refusal into a silent direct connection or an opaque clone failure — worse
# than the refusal it would have replaced. Verified before excluding: no proxy
# name appears anywhere in graphify's installed source (`grep -rq
# 'HTTP_PROXY\|HTTPS_PROXY\|ALL_PROXY\|NO_PROXY'
# .venv/lib/python3.14/site-packages/graphify/` -> absent; control
# `GEMINI_API_KEY` -> present), so excluding them from the scrub cannot open a
# non-Claude routing path — the invariant `do-not.md` #4 exists to protect is
# unaffected.
_ROUTE_OVERRIDE_PROXY_NAMES = frozenset(
    {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    }
)


class AuthIdentity(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Non-sensitive Claude subscription routing identity."""

    logged_in: bool
    auth_method: str
    api_provider: str
    subscription_type: str


class ClaudePreflight(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Read-only identity and capability proof required before inference."""

    executable: str
    executable_sha256: str
    version: str
    help_sha256: str
    required_flags: tuple[str, ...]
    auth: AuthIdentity
    environment_names: tuple[str, ...]
    graphify_runtime: RuntimeIdentity
    graphify_version: str
    graphify_semantic_fingerprint_sha256: str


class SourceIdentity(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact immutable source bytes admitted to the semantic slice."""

    source: str
    ref: str
    commit: str
    tree: str
    path: str
    git_object: str
    sha256: str
    size: int


class ArtifactMember(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One independently rehashed regular-file candidate member."""

    name: str
    sha256: str
    size: int


class ChunkEvidence(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact one-unit dispatch and result binding for the semantic call."""

    ordinal: int
    total: int
    source_path: str
    source_git_object: str
    source_sha256: str
    source_size: int
    prompt_sha256: str
    fragment_sha256: str
    node_count: int
    edge_count: int
    hyperedge_count: int


class ExecutionConfig(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact non-secret runtime controls for the one authorized call."""

    api_timeout_ms: int
    claude_code_disable_nonessential_traffic: bool
    claude_code_disable_telemetry: bool
    claude_code_max_output_tokens: int
    claude_code_max_retries: int
    max_structured_output_retries: int
    graphify_api_timeout_seconds: int
    graphify_no_incremental_cache: bool
    chunk_size: int
    token_budget: int | None
    max_concurrency: int
    max_retry_depth: int
    deep_mode: bool


class ClaudeProfile(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One reviewed provider shape: the model, its caps, and the argv it implies.

    Every field that varies between the slice and the corpus lives here, so the
    two shapes differ by DATA rather than by a second code path. The argv-literal
    fields (``max_budget_usd``, ``effort``) are strings because they are compared
    byte-for-byte against a recorded ``argv``: a float that renders as ``0.25``
    here and ``0.25000000000000001`` after a round trip would fail as a shape
    mismatch rather than as the formatting difference it really is.
    """

    name: str
    model: str
    canonical_model: str
    max_budget_usd: str
    # "" means the profile does not pass ``--effort`` at all, which is what keeps
    # the slice's committed 19-argument evidence valid rather than merely similar.
    effort: str
    max_output_tokens: str
    max_retries: str
    max_turns: str
    max_cost_usd: float

    @property
    def retained_argv_length(self) -> int:
        """Length of the ``argv`` the adapter records (the executable is dropped)."""
        return 19 + (2 if self.effort else 0)


class SemanticReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Public receipt for exactly one real Graphify-to-Claude semantic call."""

    schema_id: str
    status: str
    source: SourceIdentity
    runtime: ClaudePreflight
    adapter_metadata_sha256: str
    semantic_fragment_sha256: str
    chunks: tuple[ChunkEvidence, ...]
    execution_config: ExecutionConfig
    attempts: int
    backend: str
    model: str
    max_concurrency: int
    max_retry_depth: int
    failed_chunks: int
    uncovered_files: tuple[str, ...]
    out_of_scope_dropped: int
    semantic_node_count: int
    semantic_edge_count: int
    semantic_hyperedge_count: int
    graph_node_count: int
    graph_edge_count: int
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


class CandidateManifest(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content-addressed public manifest for one complete semantic candidate."""

    schema_id: str
    source: SourceIdentity
    members: tuple[ArtifactMember, ...]
    warnings: tuple[str, ...]


class SemanticVerification(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Fail-closed public verification verdict."""

    state: str
    structural_complete: bool
    real_semantic_complete: bool
    reasons: tuple[str, ...]


_ACCEPTED_GRAPHIFY_RUNTIME = RuntimeIdentity(
    # ADVANCED 0.9.45 -> 0.9.48 (2026-08-21): the COMMITTED EVIDENCE moved — the
    # slice was re-run at 0.9.48 in the same change, and this constant is the
    # authority for THAT receipt, so it may only advance when the receipt does.
    # Order followed, same discipline as the 0.9.44 -> 0.9.45 advance before it:
    # the pin moved, the slice re-ran and produced a 0.9.48 receipt, `verify`
    # reported `candidate-authority-mismatch` against this still-0.9.45 value
    # (the ONLY reason — `_verify_candidate` returns as soon as any manifest-level
    # reason exists, before it ever reaches the runtime-pair checks), and only
    # then did this advance.
    version="0.9.48",
    cli_version="0.9.48",
    sdk_version="0.9.48",
    executable=".venv/bin/graphify",
    sdk_fingerprint_sha256="b10406f90fe7c369fc1396991679f6e4490e59f9351332c30b9fe2216f071157",
    wheel_sha256="4f745d72d6c5165ef7132bf8b2819ef59707aa70cd99efd3a4fbc8c4ba43b4b9",
    sdist_sha256="14eaac83804866940ccb34491ca69ab62b2b51e346f88356c5211a3d8cd5e41e",
)
# The runtime a NON-authority run may additionally use. `_ACCEPTED_…` above now
# reads 0.9.48, re-attested 2026-08-21 in `a67cbac4` (cold review P2-1 — this
# paragraph said "reads 0.9.45" long after that stopped being true). It read
# 0.9.45 when this paragraph was first written, at the 0.9.44 -> 0.9.45 bump
# described below: it is the authority for whichever receipt is committed, and
# it moves only because the evidence moves, never because the pin does.
#
# `sdk_fingerprint_sha256` is UNCHANGED across 0.9.44 -> 0.9.45, and that is a
# measurement rather than a copy-forward, re-derived against the INSTALLED 0.9.45:
# `public_api_fingerprint()` hashed to b10406f9… and `semantic_api_fingerprint()`
# to 43122fca… AT THAT BUMP, both byte-identical to the 0.9.44 records — see the
# ⚠️ block below for where and why `semantic_api_fingerprint()` later moved to
# 6047cf0e… at 0.9.48 (cold review P2-1 again: citing 43122fca… with nothing
# beside it reads as current, and by 0.9.48 it no longer is);
# `public_api_fingerprint()` is still b10406f9… today. The one signature the
# semantic path depends on — `llm.extract_corpus_parallel` — did not change AT
# THIS BUMP, which is what `assert_semantic_sdk`'s "review the release before
# inference" gate is actually asking about. Cross-checked against the release
# diff: `graphify/llm.py` does not appear in `compare/v0.9.43...v0.9.45` at all,
# against a 30-file control.
#
# The wheel/sdist digests DID move, because the distribution is a new build; they
# are read from `uv.lock`, which is the same source `graphify_baseline` derives
# them from rather than a second opinion about the same artifact.
# ADVANCED to 0.9.46, and the distinction from `_ACCEPTED_GRAPHIFY_RUNTIME`
# above is the whole point: that one is FROZEN EVIDENCE about a receipt that
# already happened and may not move until the slice re-runs; this one is the
# runtime a non-authority run may additionally use, i.e. what is INSTALLED. So
# the pin bump moves this and must not move that.
#
# Leaving it behind was a LIVE break, not a cosmetic lag — the comment at the
# pairing site below says so in advance: "a literal left beside a newer runtime
# makes the pair unmatchable and the non-authority path rejects every run under
# the installed version." Found by the cold lane's round 2; the ref-binding
# check reported DRIFT and its own test could not (see
# tests/test_currency_ref_bindings.py).
#
# ADVANCED AGAIN to 0.9.47. All three digests MEASURED against the installed
# 0.9.47 via `graphify_baseline.runtime_identity`, not carried:
# `sdk_fingerprint_sha256` is UNCHANGED across 0.9.45 -> 0.9.46 -> 0.9.47 — the
# public SDK surface is identical at all three — while the wheel and sdist
# digests moved because each distribution is a new build.
#
# ⚠️ DO NOT COPY FORWARD THE 0.9.45 ARGUMENT HERE. That entry justified its
# fingerprint by noting `graphify/llm.py` "does not appear in the compare at
# all". At 0.9.47 IT DOES: `compare/v0.9.46...v0.9.47` lists 30 files and
# `graphify/llm.py` is one of them — the release fixes an `AttributeError:
# 'ThinkingBlock'` crash when an extended-thinking response leads with a
# thinking block (#2697). That is the CLAUDE backend, i.e. the only backend
# this repo permits, so it is a reason to adopt rather than a risk. What
# settles `assert_semantic_sdk`'s "review the release before inference" gate is
# the fingerprint being byte-identical: the changed code is inside the
# response-reading path, not on the signature of `llm.extract_corpus_parallel`.
# The absence-of-llm.py test would have PASSED at 0.9.45 and been FALSE here.
# ADVANCED AGAIN to 0.9.48 — and this bump is repairing a LIVE BREAK, not just
# keeping up. The 0.9.47 advance moved this object and left the literal it is
# PAIRED with at "0.9.46" (`_runtime_reasons`, below), so the pair had been
# unmatchable ever since: a real non-authority run was rejected with BOTH
# `receipt-runtime-mismatch` and `receipt-graphify-version-mismatch`.
#
# The comment beside that pairing PREDICTED this exact failure, in these words —
# "a literal left beside a newer runtime makes the pair unmatchable and the
# non-authority path rejects every run under the installed version" — and it was
# written because it had already happened once at 0.9.46. It then happened again
# one bump later, in the file that says so. A warning is not a mechanism; that is
# why this advance ships
# `test_non_authority_path_accepts_the_current_graphify_runtime`
# (tests/test_graphify_semantic_slice.py) instead of a third restatement of the
# same paragraph. (Cold review nit 4: this comment used to cite
# `test_non_authority_graphify_pairs_*`, a name that test never had.)
#
# NOTHING CAUGHT IT: the suite was rc=0 the whole time, because no test exercised
# the non-authority path. CodeRabbit did, on PR #422, after a cold cross-family
# lane and the author both read the diff and missed it.
#
# All three digests MEASURED against the installed 0.9.48 via
# `graphify_baseline.runtime_identity`, never carried:
# `sdk_fingerprint_sha256` is UNCHANGED at b10406f9… — the value 0.9.45, 0.9.46
# and 0.9.47 all recorded, so the public SDK surface is identical at four
# consecutive releases — while the wheel and sdist digests moved because each
# distribution is a new build.
#
# ⚠️ WHAT DOES NOT BELONG TO THIS CONSTANT: `semantic_api_fingerprint()` MOVED
# (43122fca… -> 6047cf0e…) at 0.9.48 because `extract_corpus_parallel`'s
# `max_retry_depth: int = 3` became `int | None = None` (upstream #2880). That
# is a different digest with a different owner —
# `_ACCEPTED_SEMANTIC_FINGERPRINT_SHA256` below — which moved in THIS round's
# re-attest once the slice re-ran under 0.9.48; see that constant's own comment.
_CURRENT_GRAPHIFY_RUNTIME = RuntimeIdentity(
    version="0.9.48",
    cli_version="0.9.48",
    sdk_version="0.9.48",
    executable=".venv/bin/graphify",
    sdk_fingerprint_sha256="b10406f90fe7c369fc1396991679f6e4490e59f9351332c30b9fe2216f071157",
    wheel_sha256="4f745d72d6c5165ef7132bf8b2819ef59707aa70cd99efd3a4fbc8c4ba43b4b9",
    sdist_sha256="14eaac83804866940ccb34491ca69ab62b2b51e346f88356c5211a3d8cd5e41e",
)
# The version the COMMITTED SLICE RECEIPT was produced under, and therefore the
# authority for it — `_receipt_reasons` compares the retained receipt against
# these three. Exactly the discipline `_ACCEPTED_GRAPHIFY_RUNTIME` states one
# constant above: it may only advance when the EVIDENCE does, never on a version
# bump alone, which would assert an identity the receipt on disk contradicts.
#
# THIS WAS ADVANCED TO 2.1.234 AND REVERTED IN THE SAME ROUND, which is the
# useful part. Claude Code self-updated, so bumping "the accepted version" looked
# like ordinary currency work; it turned the committed slice candidate from
# `unapproved` to `failed`, because that evidence was produced at 2.1.233 and no
# edit here can change what already ran. The corpus planner's need is a DIFFERENT
# question — what will run next — and it now reads `_CURRENT_CLAUDE_*` below.
# Two constants, because there are two questions.
#
# ADVANCED to 2.1.238 (2026-08-21), for the reason the paragraph above says is
# the only valid one: the COMMITTED RECEIPT was re-produced at this version, as
# part of the graphify 0.9.48 re-attest — and all three values are MEASURED from
# the same preflight that produced the new receipt. The help digest is unchanged,
# still `71ad650f…`.
#
# #464 (fixed 2026-08-23): this comment used to end "It now equals
# `_CURRENT_CLAUDE_VERSION` below". That was true for about a day. It went stale
# the moment `_CURRENT_` advanced to 2.1.240 and stayed wrong through 2.1.241 —
# a comment contradicting the constant three lines beneath it, which is the
# worst place for a stale claim to live because the reader trusts proximity.
# The two values are DIFFERENT BY DESIGN: `_ACCEPTED_` is what a committed
# receipt was produced under, `_CURRENT_` is what a new run may use. They
# converge only by coincidence, so no comment here should ever assert they are
# equal — it can only ever be a snapshot that rots.
_ACCEPTED_CLAUDE_VERSION = "2.1.238"
_ACCEPTED_CLAUDE_EXECUTABLE_SHA256 = (
    "1c196c456373b57818ae87df84aecee96cb659448c0d6a6bbb401ac5758431b2"
)
_ACCEPTED_CLAUDE_HELP_SHA256 = "71ad650f59e08ae40ede14c534db4f49d8590ee5a4f92f6da2882d3a5560fea6"

# The version a NEW run may use — what the corpus plan pins and what its preflight
# will meet. The `_ACCEPTED_`/`_CURRENT_` pair mirrors the graphify one above, for
# the same reason: one describes evidence that exists, the other declares what is
# allowed to happen next, and collapsing them makes a currency bump silently
# invalidate committed evidence.
#
# 2.1.233 -> 2.1.234. Third consecutive advance with the same shape, and the shape
# IS the review: the BINARY digest moved and the `--help` digest did NOT —
# 71ad650f… is the value 2.1.232 and 2.1.233 both recorded, so every required
# flag is spelled identically and only the implementation moved. Measured rather
# than carried forward: `--help` was re-hashed against the INSTALLED 2.1.234
# through this module's own `claude_child_environment`, so the digest compared is
# the one a real preflight computes rather than a shell's.
#
# The 2.1.226 -> 2.1.234 release review lives in `currency.toml`'s
# `[tool.claude-code]` block. Nothing in those eight releases touches the flags,
# the argv shape or the envelope this path depends on.
#
# 2.1.234 -> 2.1.235 advanced 2026-08-19 alongside `currency.toml`'s `expected`,
# because `claude` self-updates in place and the binary on PATH had already moved
# — so leaving this at 2.1.234 asserted an identity the host contradicts. Both
# values are MEASURED here, not carried: `claude --version` reports 2.1.235 and
# `shasum -a 256 $(command -v claude)` reports the digest below.
#
# It is the ELEVENTH version-restatement site in this package and the cold lane
# found it, not the ref-binding check — that check compares against
# `sources/graphify.manifest`, so a claude-code binding is outside its scope
# entirely. Worth stating plainly: the currency machinery does not see this line.
#
# 2.1.235 -> 2.1.236 advanced 2026-08-19, for the same reason and by the same
# measurement: `claude` self-updated in place again, so the sweep that moved
# `currency.toml`'s `expected` and `sources/claude-code.manifest` had to move
# this too or it would assert an identity the host contradicts. Measured, not
# carried: `claude --version` reports 2.1.236 and the digest below is
# `sha256(Path(which("claude")).read_bytes())`.
#
# THE `--help` DIGEST DID NOT MOVE — re-hashed against the INSTALLED 2.1.236
# through this module's own `claude_child_environment`, it is still
# 71ad650f…, the value 2.1.232 through 2.1.235 all recorded. So every flag this
# path depends on is spelled identically and only the implementation moved,
# which is the fourth consecutive advance with that shape.
#
# AND THE CURRENCY MACHINERY STILL DOES NOT SEE THIS LINE. The paragraph above
# recorded that once; this bump proves it was not a one-off. The claude-code
# sweep moved four files and left this constant behind, `kb-currency-check`
# reported nothing, and the COLD LANE found it a SECOND time (P0, review of
# fe57f996). Two independent misses by the same blind spot is not an anecdote —
# it is the evidence for #393, which is why that issue cites it.
#
# 2.1.236 -> 2.1.238 advanced 2026-08-20. `claude` self-updated in place TWICE
# (2.1.237 was never installed here long enough to be recorded), so leaving this
# at 2.1.236 asserted an identity the host contradicts and the corpus preflight
# would have refused. Measured, not carried, and through this module's OWN
# `claude_child_environment` rather than a shell — `shutil.which("claude")`
# resolves to `~/.local/share/claude/versions/2.1.238`, `--version` reports
# `2.1.238 (Claude Code)`, and the digest below is
# `sha256(Path(which("claude")).read_bytes())`.
#
# THE `--help` DIGEST DID NOT MOVE — still 71ad650f…, the value 2.1.232 through
# 2.1.236 all recorded, re-hashed against the INSTALLED 2.1.238. So every flag
# this path depends on is spelled identically and only the implementation moved.
# That is the FIFTH consecutive advance with this shape, which is the whole
# reason the shape is worth stating: it is what makes a version bump a
# re-record rather than a review.
#
# 2.1.238 -> 2.1.240 advanced 2026-08-22, same shape, SIXTH consecutive. Measured
# through this module's own `claude_child_environment`, not a shell:
# `--version` reports `2.1.240 (Claude Code)` and the digest below is
# `sha256(Path(which("claude")).read_bytes())`.
#
# `shutil.which("claude")` now answers `~/.local/bin/claude` where the note above
# says `~/.local/share/claude/versions/2.1.238`. NOT an installer-layout change:
# `~/.local/bin/claude` is a SYMLINK to `~/.local/share/claude/versions/2.1.240`,
# and `Path.read_bytes()` follows it, so the digest is of the same target file
# either way. Recorded because two different-looking paths across two notes is
# exactly the shape someone re-derives.
#
# THE `--help` DIGEST DID NOT MOVE — still 71ad650f…, the value 2.1.232 through
# 2.1.241 all recorded, re-hashed against the INSTALLED 2.1.241. So every flag
# this path depends on is spelled identically and only the implementation moved.
#
# 2.1.241 (2026-08-23): hashed live before the bump rather than assumed, because
# the help digest is an ALIAS of `_ACCEPTED_CLAUDE_HELP_SHA256` below — had it
# moved, this would not have been a two-constant edit. `claude --help | shasum
# -a 256` returned 71ad650f… byte-identical, so the alias stands.
_CURRENT_CLAUDE_VERSION = "2.1.241"
_CURRENT_CLAUDE_EXECUTABLE_SHA256 = (
    "1495eb7c42d3b4451f5f1cd38b6d498d22a4a38c802bc2be5c1cf1795e64820d"
)
_CURRENT_CLAUDE_HELP_SHA256 = _ACCEPTED_CLAUDE_HELP_SHA256
# ADVANCED 43122fca… -> 6047cf0e… (2026-08-21): the value the re-run's own
# preflight measured under graphify 0.9.48 (see the runtime comment above for
# why it moved). Same discipline as `_ACCEPTED_GRAPHIFY_RUNTIME` — may only
# advance when the receipt does.
_ACCEPTED_SEMANTIC_FINGERPRINT_SHA256 = (
    "6047cf0eeec29b0fc7d1730a5e45f21b9765bbf4b71c34226b4040a2fcd987f9"
)
_ACCEPTED_EXECUTION_CONFIG = ExecutionConfig(
    api_timeout_ms=120_000,
    claude_code_disable_nonessential_traffic=True,
    claude_code_disable_telemetry=True,
    claude_code_max_output_tokens=4096,
    claude_code_max_retries=0,
    max_structured_output_retries=1,
    graphify_api_timeout_seconds=120,
    graphify_no_incremental_cache=True,
    chunk_size=1,
    token_budget=None,
    max_concurrency=1,
    max_retry_depth=0,
    deep_mode=False,
)


# The shape #300 actually ran under. Every value here is transcribed from the
# committed candidate, not chosen — this profile is a description of evidence, so
# it may only change when the slice is re-run and its receipt re-committed.
SLICE_PROFILE = ClaudeProfile(
    name="slice",
    model=_CLAUDE_MODEL,
    canonical_model=_CLAUDE_CANONICAL_MODEL,
    max_budget_usd="0.25",
    effort="",
    max_output_tokens="4096",
    max_retries="0",
    max_turns="3",
    max_cost_usd=_MAX_COST_USD,
)
# The shape the whole-tree corpus run uses (Ray, 2026-08-16). Three of these
# differ from the slice for reasons worth stating, because each looks like a
# preference and is not:
#
# * `claude-opus-5` — the corpus is this project's core dependency and the graph
#   every other agent queries, so the extraction is long-lived and expensive to
#   redo. Opus is the tier chosen for that, deliberately, once.
# * `max_output_tokens` 4096 -> 8192 — NOT a richness preference. Thinking is on
#   by default on Opus 5 and shares this cap with the response text, so 4096
#   against an ~18k-token markdown chunk truncates the structured extraction
#   mid-object. The slice keeps 4096 because haiku at 4096 is what it measured.
# * `max_retries` 0 -> 2 — 57 chunks make a single transient failure likely
#   rather than hypothetical, and a lost chunk is a silent hole in the corpus.
CORPUS_PROFILE = ClaudeProfile(
    name="corpus",
    model="claude-opus-5",
    canonical_model="claude-opus-5",
    max_budget_usd="25.00",
    effort="high",
    max_output_tokens="8192",
    max_retries="2",
    max_turns="3",
    max_cost_usd=25.0,
)
_PROFILES = {profile.name: profile for profile in (SLICE_PROFILE, CORPUS_PROFILE)}


def profile_for(environment: Mapping[str, str]) -> ClaudeProfile:
    """Resolve the reviewed profile named by the environment, failing closed.

    An absent variable selects the slice — the narrower shape — so a launcher that
    simply FORGETS to name its profile cannot silently inherit the corpus's model
    and spend cap. An unrecognized value is an error rather than a fallback, for
    the same reason: quietly treating a typo as "slice" would report a run that
    used one shape as evidence about another.
    """
    name = environment.get(PROFILE_ENV_NAME, SLICE_PROFILE.name)
    profile = _PROFILES.get(name)
    if profile is None:
        raise ValueError(f"unknown semantic profile: {name}")
    return profile


class ClaudeIdentity(msgspec.Struct, frozen=True):
    """A reviewed Claude Code identity, as one value rather than three literals."""

    version: str
    executable_sha256: str
    help_sha256: str


def current_claude() -> ClaudeIdentity:
    """Return the Claude Code identity a NEW run may use.

    Not `_ACCEPTED_CLAUDE_*`, and the difference is the whole point. Those three
    are the authority for the COMMITTED slice receipt — evidence about a run that
    already happened, which no edit here can change. This is a declaration about
    what is allowed to happen next, which is what the corpus planner pins.
    Reading the wrong one turned the committed slice candidate from `unapproved`
    to `failed` during this round's currency bump.

    Public because `graphify_semantic_corpus` needs these values and used to
    TRANSCRIBE them — three literals here, three more there, bound only by a
    comment saying "kept in step". That module has already paid for that pattern
    once: a transcribed `graphify_version` read 0.9.43 while the runtime constant
    beside it read 0.9.44, so every plan written after that pin bump recorded two
    different versions for one run.

    A struct rather than a 3-tuple because all three fields are `str` and two are
    hex digests: unpacked positionally, the executable and help digests could be
    transposed without a type error, and the resulting plan would pin a contract
    nobody reviewed while verifying as internally consistent.
    """
    return ClaudeIdentity(
        version=_CURRENT_CLAUDE_VERSION,
        executable_sha256=_CURRENT_CLAUDE_EXECUTABLE_SHA256,
        help_sha256=_CURRENT_CLAUDE_HELP_SHA256,
    )


def accepted_graphify_runtime() -> RuntimeIdentity:
    """Return the reviewed Graphify runtime identity from ``_ACCEPTED_GRAPHIFY_RUNTIME``.

    Ask the constant for the version. This docstring names none, deliberately:
    it used to restate one, went stale across two releases, and both attempts to
    repair it wrote fresh version numbers into the sentence declaring that it
    contained none — so each fix was self-refuting on the line below its own
    claim, and the second reinstated the drift it described. The constant
    (originally reviewed under issue #300) is the single place the version lives.
    """
    return _ACCEPTED_GRAPHIFY_RUNTIME


def encode_json(value: object) -> bytes:
    """Encode one public evidence object canonically enough for hashing."""
    return msgspec.json.encode(value, order="sorted")


def _is_sha256(value: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", value) is not None


def sha256_file(path: Path) -> str:
    """Hash one file without retaining its full contents in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


MAX_OUTPUT_TOKENS_ENV_NAME = "KB_SEMANTIC_MAX_OUTPUT_TOKENS"


def resolved_max_output_tokens(environment: Mapping[str, str], profile: ClaudeProfile) -> str:
    """Return the plan's pinned output cap, or the profile's own literal.

    The corpus driver exports the value its PLAN recorded, resolved once from the
    model's real ceiling; the profile literal is what a launcher with no plan
    behind it gets. The profile's value is the LOWER of the two, so falling back
    to it can only under-spend — the safe direction for an absent variable.

    A malformed value RAISES rather than falling back, because a typo silently
    reverting to the literal is exactly the failure this replaces: an
    unnoticed low cap truncates a structured extraction mid-object, and the run
    reports a refusal whose cause is nowhere in the evidence.
    """
    raw = environment.get(MAX_OUTPUT_TOKENS_ENV_NAME, "")
    if not raw:
        return profile.max_output_tokens
    if not raw.isdigit() or int(raw) <= 0:
        raise ValueError(f"{MAX_OUTPUT_TOKENS_ENV_NAME} is not a positive integer")
    return raw


def child_control_env(
    profile: ClaudeProfile, max_output_tokens: str | None = None
) -> dict[str, str]:
    """Return the control variables for one profile.

    The NAMES are identical across profiles and only the values move, which is
    what lets the receipt keep comparing ``environment_names`` unchanged while the
    corpus raises its own caps. That property is why the pinned output cap arrives
    as a VALUE override here rather than as a new variable: a new name in the
    child environment would move ``environment_names`` and invalidate the
    committed slice evidence, for a fact the plan already records.
    """
    return {
        **_CHILD_CONTROL_ENV,
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": (
            profile.max_output_tokens if max_output_tokens is None else max_output_tokens
        ),
        "CLAUDE_CODE_MAX_RETRIES": profile.max_retries,
    }


def claude_child_environment(
    environment: Mapping[str, str],
    *,
    original_path: str | None = None,
    profile: ClaudeProfile | None = None,
) -> dict[str, str]:
    """Build the fixed OAuth-compatible environment used for auth and inference."""
    child = {
        name: environment[name]
        for name in _CHILD_BASE_ENV_NAMES
        if environment.get(name) is not None
    }
    child["PATH"] = original_path if original_path is not None else environment.get("PATH", "")
    selected = profile if profile is not None else SLICE_PROFILE
    child.update(child_control_env(selected, resolved_max_output_tokens(environment, selected)))
    return child


def expected_adapter_argv(
    profile: ClaudeProfile, schema: str, *, with_max_turns: bool = True
) -> tuple[str, ...]:
    """Return the exact recorded ``argv`` one profile's boundary call must have.

    ONE definition, three callers: the adapter builds the outgoing call from it,
    and the slice and corpus verifiers each re-check a recorded ``argv`` against
    it. Keeping them a single function is the point — a fourth spelling of this
    tuple is how a shape check starts agreeing with itself instead of with the
    call that actually ran.

    ``with_max_turns`` exists only for the adapter's no-boundary-marker branch,
    which yields the historical #300 shape. Both verifiers leave it at ``True``:
    both launchers configure the marker, so a recorded run without those two
    arguments is a real shape mismatch and must be reported as one.
    """
    return (
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        profile.model,
        "--json-schema",
        schema,
        "--safe-mode",
        "--tools",
        "",
        "--strict-mcp-config",
        "--permission-mode",
        "dontAsk",
        "--no-chrome",
        "--max-budget-usd",
        profile.max_budget_usd,
        *(("--max-turns", profile.max_turns) if with_max_turns else ()),
        *(("--effort", profile.effort) if profile.effort else ()),
    )


def recorded_schema(argv: tuple[str, ...], profile: ClaudeProfile) -> str:
    """Return the schema argument, or ``""`` when the recorded shape is wrong.

    The length guard is what makes the empty return meaningful: reading index 7
    out of an argv of the wrong length would yield some OTHER argument and then
    fail as a schema-digest mismatch, reporting a shape error in the vocabulary
    of a content error.
    """
    return argv[7] if len(argv) == profile.retained_argv_length else ""


def route_override_names(environment: Mapping[str, str]) -> tuple[str, ...]:
    """Return only forbidden routing variable names; never inspect their values."""
    return tuple(sorted(name for name in environment if name in _ROUTE_OVERRIDE_NAMES))


def scrub_route_overrides(
    environment: MutableMapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Delete every forbidden ROUTING name so the refusal never has to fire (#334).

    `preflight`'s routing check is untouched and still raises on any of the
    full 37-name `_ROUTE_OVERRIDE_NAMES` set this misses — that refusal is the
    backstop, not the mechanism. This is the mechanism: every CLI entry that
    reaches `preflight` calls this FIRST, so the ambient `AWS_*`/`ANTHROPIC_*`
    names an ordinary login shell carries cannot reach it in the first place,
    rather than relying on an operator to remember `env -u` at every launch.
    Every call site passes the return value to `report_routing_scrub` (never
    the values themselves) so a run that had to remove something and a run
    that never had anything to remove are no longer byte-indistinguishable
    after the fact — this function stays silent itself; it only deletes and
    returns what it deleted, to its own caller.

    Deletes, never reads — reuses `route_override_names` for the candidate set
    and only ever calls `del`, so this cannot leak a value it never inspected.

    EXCLUDES the four proxy variables (`HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`/
    `NO_PROXY`) from the 37-name set, scrubbing only the remaining 33
    (cold review P2-4; see `_ROUTE_OVERRIDE_PROXY_NAMES`'s own comment for the
    full reasoning). `preflight` keeps refusing all 37, proxies included —
    only the SCRUB leaves them alone. A prior version of this docstring
    justified scrubbing the proxies too by pointing at
    `claude_child_environment`'s allowlist: true of the `claude` CHILD, which
    never copies a proxy name regardless of what this function does, but
    irrelevant to what this function actually mutates — `os.environ` for THIS
    process, which is also what `git` (`_admit_source`) and the in-process
    graphify SDK's httpx client (`trust_env=True`) read. Scrubbing the
    parent's proxy configuration changed THEIR egress, not the child's, which
    is why it no longer happens.

    Defaults to the REAL process environment, deliberately: a `claude` child
    inherits `os.environ`, not a filtered mapping handed only to `preflight`, so
    scrubbing anything less would leave the forbidden names live for every
    subprocess this module spawns. Idempotent — a second call finds nothing
    left to remove and returns `()`.
    """
    target = os.environ if environment is None else environment
    removed = tuple(
        name for name in route_override_names(target) if name not in _ROUTE_OVERRIDE_PROXY_NAMES
    )
    for name in removed:
        del target[name]
    return removed


def report_routing_scrub(site: str, removed: tuple[str, ...]) -> None:
    """Emit a WARNING naming the routing names `site`'s scrub removed (never their values).

    Every `scrub_route_overrides()` call site (`build_candidate`, `semantic_main`
    here, and `graphify_semantic_corpus_run.execute`) passes its return value
    straight here. Before this existed, all three discarded it as a bare
    statement, so a host that had a forbidden name scrubbed produced a receipt
    byte-indistinguishable from a host that never had one — the refusal
    `preflight` still carries could not fire from any production caller,
    because the scrub always ran first (cold review P1-1). A no-op call
    (`removed == ()`) emits nothing, matching a clean host's silence — this is
    the one place that decision lives, so every call site's own complexity
    stays a single line.
    """
    if not removed:
        return
    events.warn(
        "semantic.routing_scrub",
        f"{site}: scrubbed forbidden routing environment names: " + ", ".join(removed),
        names=removed,
    )


def classify_auth(raw: bytes) -> AuthIdentity:
    """Reduce `claude auth status` JSON to the accepted non-sensitive fields."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Claude auth status is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError("Claude auth status is not an object")
    identity = AuthIdentity(
        logged_in=payload.get("loggedIn") is True,
        auth_method=str(payload.get("authMethod", "")),
        api_provider=str(payload.get("apiProvider", "")),
        subscription_type=str(payload.get("subscriptionType", "")),
    )
    if (
        not identity.logged_in
        or identity.auth_method != "claude.ai"
        or identity.api_provider != _CLAUDE_PROVIDER
        or identity.subscription_type != "max"
    ):
        raise ValueError("Claude auth is not claude.ai first-party Max")
    return identity


def _completed_bytes(executable: Path, *args: str, environment: Mapping[str, str]) -> bytes:
    completed = subprocess.run(
        [str(executable), *args],
        capture_output=True,
        check=False,
        env=dict(environment),
        timeout=30,
    )
    if completed.returncode != 0 or completed.stderr:
        raise ValueError(f"Claude {' '.join(args)} preflight failed")
    return completed.stdout


def _assert_value_flag_supported(
    executable: Path,
    flag: str,
    *,
    environment: Mapping[str, str],
) -> None:
    """Prove a hidden value-taking CLI flag at parser time without inference."""
    invalid_value = "not-an-integer"
    completed = subprocess.run(
        [str(executable), "-p", flag, invalid_value],
        capture_output=True,
        check=False,
        env=dict(environment),
        timeout=30,
    )
    diagnostic = completed.stderr
    if (
        completed.returncode != 1
        or completed.stdout
        or flag.encode() not in diagnostic
        or invalid_value.encode() not in diagnostic
        or b"is invalid" not in diagnostic
        or b"must be a number" not in diagnostic
    ):
        raise ValueError(f"Claude {flag} parser probe failed")


def _assert_effort_supported(
    executable: Path,
    level: str,
    *,
    environment: Mapping[str, str],
) -> None:
    """Prove ``--effort`` is parsed AND that ``level`` is one of its accepted values.

    ``_assert_value_flag_supported`` cannot do this job: it asserts the parser
    said "must be a number", and ``--effort`` takes a level name. Measured on the
    installed 2.1.233, the three outcomes are distinguishable and the probe is
    armed against all of them — an unknown FLAG says ``unknown option``, a valid
    LEVEL emits no warning at all, and only an invalid level produces the
    ``Unknown --effort value`` line that also enumerates the accepted set.

    That enumeration is the reason this checks the level and not merely the flag.
    An unrecognized value is **not** rejected: the CLI warns, discards it, and
    runs at the DEFAULT effort. A profile with a typo'd level would therefore
    produce a complete, plausible, fully-verified run at the wrong effort, with
    the mistake visible only in a warning nothing reads.
    """
    completed = subprocess.run(
        [str(executable), "-p", "--effort", "not-a-level"],
        capture_output=True,
        check=False,
        env=dict(environment),
        timeout=30,
    )
    diagnostic = completed.stderr.decode("utf-8", errors="strict")
    marker = "Valid values:"
    if (
        completed.returncode != 1
        or completed.stdout
        or "Unknown --effort value" not in diagnostic
        or marker not in diagnostic
    ):
        raise ValueError("Claude --effort parser probe failed")
    accepted = {
        item.strip().rstrip(".")
        for item in diagnostic.split(marker, 1)[1].split("\n", 1)[0].split(",")
    }
    if level not in accepted:
        raise ValueError(f"Claude --effort level is unavailable: {level}")


def preflight(
    repo_root: Path,
    environment: Mapping[str, str] | None = None,
    *,
    # A TENTH restatement of the pinned revision, and the only one that is a
    # function default rather than a module constant — which is why no
    # `ref_binding` row reaches it and why it lagged silently. It feeds
    # `assert_semantic_sdk`, so a stale value asks "is the semantic API the one
    # 0.9.44 shipped?" while a newer release is installed: a version gate
    # checking the wrong version, which passes for exactly as long as nothing
    # moves.
    #
    # It is no longer a literal. At the 0.9.46 bump it lagged AGAIN, exactly as
    # the paragraph above predicted, and the prediction is the reason it is now
    # READ: this default is about the runtime that will RUN, so it belongs to
    # `graphify_baseline.ACCEPTED_GRAPHIFY_VERSION` — the constant the installed
    # binary is separately asserted to match. It is deliberately NOT bound to
    # `_ACCEPTED_GRAPHIFY_RUNTIME.version` below, which is frozen evidence about a
    # receipt that already happened and may only move when that receipt is
    # re-produced.
    graphify_version: str = graphify_baseline.ACCEPTED_GRAPHIFY_VERSION,
    require_max_turns: bool = False,
    profile: ClaudeProfile = SLICE_PROFILE,
) -> ClaudePreflight:
    """Prove exact Graphify/Claude/auth/routing capability without inference."""
    from kb_setup import graphify_baseline, graphify_env, graphify_sdk

    current = dict(os.environ if environment is None else environment)
    overrides = route_override_names(current)
    if overrides:
        raise ValueError("forbidden routing environment names: " + ", ".join(overrides))
    graphify_env.assert_pinned_graphify(repo_root)
    graphify_sdk.assert_semantic_sdk(graphify_version)
    resolved = shutil.which("claude", path=current.get("PATH"))
    if not resolved:
        raise ValueError("Claude Code CLI is unavailable")
    executable = Path(resolved).resolve()
    child = claude_child_environment(current, profile=profile)
    help_raw = _completed_bytes(executable, "--help", environment=child)
    help_text = help_raw.decode("utf-8", errors="strict")
    missing = tuple(flag for flag in _REQUIRED_CLAUDE_FLAGS if flag not in help_text)
    if missing:
        raise ValueError("Claude Code required flags are unavailable: " + ", ".join(missing))
    required_flags = _REQUIRED_CLAUDE_FLAGS
    if require_max_turns:
        _assert_value_flag_supported(executable, "--max-turns", environment=child)
        required_flags = (*required_flags, "--max-turns")
    # Proven in the same run that will pass it, on `--max-turns`' precedent: a
    # flag present in `--help` is not a flag the installed binary accepts with a
    # value, and the corpus profile is the first thing here to pass `--effort`.
    if profile.effort:
        _assert_effort_supported(executable, profile.effort, environment=child)
        required_flags = (*required_flags, "--effort")
    version_raw = _completed_bytes(executable, "--version", environment=child)
    version_text = version_raw.decode("utf-8", errors="strict").strip()
    match = re.search(r"\b\d+\.\d+\.\d+\b", version_text)
    if match is None:
        raise ValueError("Claude Code version is unparsable")
    auth_raw = _completed_bytes(executable, "auth", "status", environment=child)
    fingerprint = encode_json(graphify_sdk.semantic_api_fingerprint())
    return ClaudePreflight(
        executable="claude",
        executable_sha256=sha256_file(executable),
        version=match.group(0),
        help_sha256=hashlib.sha256(help_raw).hexdigest(),
        required_flags=required_flags,
        auth=classify_auth(auth_raw),
        environment_names=tuple(sorted(child)),
        graphify_runtime=graphify_baseline.runtime_identity(repo_root),
        graphify_version=graphify_sdk.running_sdk_version(),
        graphify_semantic_fingerprint_sha256=hashlib.sha256(fingerprint).hexdigest(),
    )


def _list_is_empty(value: object) -> bool:
    return isinstance(value, list) and not value


# The reason a TRUNCATED result earns, kept apart from `stop-reason-invalid`.
# Both are refusals — a truncated structured output is not evidence — but only
# this one is RECOVERABLE, by extracting the chunk in halves. Collapsing them
# left the plan's `graphify_max_retry_depth=2` inert for the single failure it
# was raised to survive, because the adapter refused the envelope before
# graphify could translate `stop_reason=max_tokens` into `finish_reason=length`
# and bisect. See `TRUNCATION_RETRY_HINT`.
TRUNCATED_STOP_REASON = "stop-reason-truncated"

# Emitted on stderr alongside the refusal so graphify's `_looks_like_context_exceeded`
# classifies our non-zero exit as a context overflow and its adaptive retry
# bisects the chunk instead of dropping it.
#
# Substring matching against that helper's marker list is graphify's OWN
# extension point, not a private detail being reached into: it matches on
# stringified-exception substrings precisely "so the retry layer can recover
# without depending on a specific SDK class" (`graphify/llm.py`). It is still
# coupling, so a test asserts the pinned graphify actually classifies this
# string — if upstream rewords its markers, that test fails rather than this
# recovery going quietly dead.
TRUNCATION_RETRY_HINT = (
    "the model stopped at max_completion_tokens: this chunk's prompt is too long "
    "for one response and must be extracted in halves"
)


def truncation_retry_hint(reasons: tuple[str, ...]) -> str | None:
    """Return the stderr line that makes a truncation refusal legible, else None.

    A function rather than an inline conditional in the adapter because that is
    the only form of this decision a test can reach: the adapter's own copy lives
    between a subprocess call and a `sys.exit`, so nothing covered it, and a
    mutation that simply deleted the print would have survived every arm while
    silently restoring the defect.
    """
    return TRUNCATION_RETRY_HINT if TRUNCATED_STOP_REASON in reasons else None


def _result_reasons(
    envelope: dict[str, object],
    *,
    max_turns: int | None = _MAX_TURNS_WITH_ONE_STRUCTURED_REPAIR,
) -> list[str]:
    reasons = []
    stop_reason = envelope.get("stop_reason")
    checks = (
        (envelope.get("type") == "result", "result-type-invalid"),
        (envelope.get("subtype") == "success", "result-subtype-invalid"),
        (envelope.get("is_error") is False, "result-error"),
        (envelope.get("terminal_reason") == "completed", "terminal-state-invalid"),
        (
            stop_reason in {"end_turn", "tool_use"},
            TRUNCATED_STOP_REASON if stop_reason == "max_tokens" else "stop-reason-invalid",
        ),
    )
    reasons.extend(reason for accepted, reason in checks if not accepted)
    turns = envelope.get("num_turns")
    if (
        isinstance(turns, bool)
        or not isinstance(turns, int)
        or turns < 1
        or (max_turns is not None and turns > max_turns)
    ):
        reasons.append("turn-bound-exceeded")
    return reasons


def _structured_reasons(envelope: dict[str, object]) -> list[str]:
    structured = envelope.get("structured_output")
    if not isinstance(structured, dict):
        return ["structured-output-missing"]
    if not isinstance(structured.get("nodes"), list) or not isinstance(
        structured.get("edges"), list
    ):
        return ["structured-output-invalid"]
    return []


def _model_reasons(envelope: dict[str, object], profile: ClaudeProfile) -> list[str]:
    """Check the envelope reports exactly the model this PROFILE asked for.

    Profile-driven rather than pinned to the module constants, which is the
    second instance of one class: the slice's identity leaking into a corpus code
    path. Under `CORPUS_PROFILE` the response reports `claude-opus-5`, so the
    hardcoded haiku comparison rejected it as `model-identity-invalid` and the
    adapter refused every corpus chunk — a whole-corpus failure whose message
    named the model rather than the check.

    Still an exact single-model comparison: the point of the check is that ONE
    reviewed model answered, and a response listing two is a routing surprise
    whichever they are.
    """
    model_usage = envelope.get("modelUsage")
    if not isinstance(model_usage, dict) or tuple(model_usage) != (profile.model,):
        return ["model-identity-invalid"]
    model = model_usage[profile.model]
    if not isinstance(model, dict) or (model.get("canonicalModel"), model.get("provider")) != (
        profile.canonical_model,
        _CLAUDE_PROVIDER,
    ):
        return ["model-identity-invalid"]
    return []


def _negative_evidence_reasons(envelope: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    if not _list_is_empty(envelope.get("permission_denials")):
        reasons.append("permission-denial-present")
    errors = envelope.get("errors")
    if errors is not None and not _list_is_empty(errors):
        reasons.append("error-present")
    for key, reason in (
        ("warnings", "warning-present"),
        ("fallback_models", "fallback-model-present"),
        ("routing_overrides", "routing-override-present"),
        ("external_tools", "external-tool-present"),
    ):
        if envelope.get(key, []) not in (None, [], {}):
            reasons.append(reason)
    return reasons


def envelope_reasons(
    envelope: object,
    *,
    max_turns: int | None = _MAX_TURNS_WITH_ONE_STRUCTURED_REPAIR,
    profile: ClaudeProfile = SLICE_PROFILE,
) -> tuple[str, ...]:
    """Explain why a redacted real Claude result envelope cannot be accepted."""
    if not isinstance(envelope, dict):
        return ("result-envelope-invalid",)
    reasons = [
        *_result_reasons(envelope, max_turns=max_turns),
        *_structured_reasons(envelope),
        *_model_reasons(envelope, profile),
        *_negative_evidence_reasons(envelope),
    ]
    return tuple(dict.fromkeys(reasons))


def _records(value: object) -> list[dict[str, object]] | None:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        return None
    return value


def _hyperedge_invalid(hyperedges: list[dict[str, object]], known_ids: set[str]) -> bool:
    for hyperedge in hyperedges:
        member_ids = hyperedge.get("nodes")
        if (
            not isinstance(member_ids, list)
            or not member_ids
            or any(not isinstance(node_id, str) or not node_id for node_id in member_ids)
            or any(node_id not in known_ids for node_id in member_ids)
        ):
            return True
    return False


def _fragment_source_reasons(
    records: list[dict[str, object]], source_paths: tuple[str, ...]
) -> list[str]:
    accepted_paths = set(source_paths)
    raw_observed_paths = [item.get("source_file") for item in records]
    observed_paths = {path for path in raw_observed_paths if isinstance(path, str) and path}
    invalid_scope = (
        not source_paths
        or len(accepted_paths) != len(source_paths)
        or any(not isinstance(path, str) or not path for path in source_paths)
        or any(not isinstance(path, str) or not path for path in raw_observed_paths)
        or not observed_paths.issubset(accepted_paths)
    )
    reasons = ["fragment-source-scope-mismatch"] if invalid_scope else []
    if observed_paths != accepted_paths:
        reasons.append("fragment-source-coverage-mismatch")
    return reasons


def fragment_scope_reasons(fragment: object, *, source_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Validate structure, provenance, scope, and references for semantic records."""
    if not isinstance(fragment, dict):
        return ("fragment-invalid",)
    nodes = _records(fragment.get("nodes"))
    edges = _records(fragment.get("edges"))
    hyperedges = _records(fragment.get("hyperedges", []))
    if nodes is None or edges is None or hyperedges is None:
        return ("fragment-schema-invalid",)
    reasons: list[str] = []
    node_ids = [node.get("id") for node in nodes]
    if not nodes:
        reasons.append("zero-semantic-nodes")
    if any(not isinstance(node_id, str) or not node_id for node_id in node_ids):
        reasons.append("semantic-node-identity-invalid")
    valid_node_ids = [node_id for node_id in node_ids if isinstance(node_id, str) and node_id]
    if len(valid_node_ids) != len(set(valid_node_ids)):
        reasons.append("duplicate-semantic-node-identity")
    known_ids = set(valid_node_ids)
    records = [*nodes, *edges, *hyperedges]
    if any(item.get("_origin") not in (None, "semantic") for item in records):
        reasons.append("fragment-origin-invalid")
    reasons.extend(_fragment_source_reasons(records, source_paths))
    if any(
        not isinstance(edge.get("source"), str)
        or not isinstance(edge.get("target"), str)
        or edge.get("source") not in known_ids
        or edge.get("target") not in known_ids
        for edge in edges
    ):
        reasons.append("unresolved-edge-endpoint")
    if _hyperedge_invalid(hyperedges, known_ids):
        reasons.append("unresolved-hyperedge-member")
    return tuple(dict.fromkeys(reasons))


def fragment_reasons(fragment: object, *, source_path: str) -> tuple[str, ...]:
    """Validate one-source fragment structure, provenance, scope, and references."""
    return fragment_scope_reasons(fragment, source_paths=(source_path,))


def expected_source_identity() -> SourceIdentity:
    """Return the reviewed trust root for the single #300 source document."""
    return SourceIdentity(
        source="graphify",
        ref=SOURCE_REF,
        commit=SOURCE_COMMIT,
        tree=SOURCE_TREE,
        path=SOURCE_PATH,
        git_object=SOURCE_GIT_OBJECT,
        sha256=SOURCE_SHA256,
        size=SOURCE_SIZE,
    )


def _candidate_entry_reasons(candidate: Path) -> list[str]:
    try:
        entries = tuple(candidate.iterdir())
    except OSError:
        return ["candidate-unavailable"]
    expected = {*_REQUIRED_MEMBERS, "manifest.json"}
    names = {entry.name for entry in entries}
    reasons = [f"candidate-entry-mismatch:{name}" for name in sorted(names ^ expected)]
    for entry in entries:
        try:
            mode = entry.lstat().st_mode
        except OSError:
            reasons.append(f"candidate-entry-unreadable:{entry.name}")
            continue
        if not stat.S_ISREG(mode):
            reasons.append(f"candidate-entry-not-regular:{entry.name}")
    return reasons


def _manifest_reasons(manifest: CandidateManifest) -> list[str]:
    names = tuple(member.name for member in manifest.members)
    reasons: list[str] = []
    if manifest.schema_id != _CANDIDATE_SCHEMA:
        reasons.append("manifest-schema-mismatch")
    if manifest.source != expected_source_identity():
        reasons.append("manifest-source-identity-mismatch")
    if names != tuple(sorted(_REQUIRED_MEMBERS)):
        reasons.append("manifest-member-set-mismatch")
    if len(names) != len(set(names)):
        reasons.append("manifest-member-duplicate")
    if manifest.warnings:
        reasons.append("manifest-warning-bearing")
    return reasons


def _member_reasons(
    candidate: Path, manifest: CandidateManifest
) -> tuple[list[str], dict[str, bytes]]:
    reasons: list[str] = []
    payloads: dict[str, bytes] = {}
    for member in manifest.members:
        path = candidate / member.name
        try:
            raw = path.read_bytes()
        except OSError:
            reasons.append(f"member-unavailable:{member.name}")
            continue
        payloads[member.name] = raw
        if len(raw) != member.size:
            reasons.append(f"member-size-mismatch:{member.name}")
        if hashlib.sha256(raw).hexdigest() != member.sha256:
            reasons.append(f"member-digest-mismatch:{member.name}")
    return reasons, payloads


def _adapter_reasons(metadata: object, receipt: SemanticReceipt, fragment: object) -> list[str]:
    from kb_setup.graphify_semantic_adapter import AdapterMetadata, parse_observation_reasons

    if not isinstance(metadata, AdapterMetadata):
        return ["adapter-metadata-schema-mismatch"]
    reasons: list[str] = []
    expected_auth = AuthIdentity(
        logged_in=True,
        auth_method="claude.ai",
        api_provider=_CLAUDE_PROVIDER,
        subscription_type="max",
    )
    checks = (
        (metadata.schema_id == "graphify-claude-boundary/v0", "adapter-schema-mismatch"),
        (metadata.status == "complete", "adapter-incomplete"),
        (metadata.claude_executable == "claude", "adapter-executable-name-mismatch"),
        (
            metadata.claude_version == f"{receipt.runtime.version} (Claude Code)",
            "adapter-version-mismatch",
        ),
        (metadata.auth == expected_auth, "adapter-auth-mismatch"),
        (metadata.returncode == 0, "adapter-returncode-nonzero"),
        (metadata.stderr_size == 0, "adapter-stderr-present"),
        (
            metadata.stderr_sha256 == hashlib.sha256(b"").hexdigest(),
            "adapter-stderr-digest-mismatch",
        ),
        (metadata.reasons == (), "adapter-rejected-result"),
        (metadata.attempt == 1, "adapter-attempt-mismatch"),
        (metadata.permission_denial_count == 0, "adapter-permission-denial-present"),
        (metadata.result_type == "result", "adapter-result-type-mismatch"),
        (metadata.result_subtype == "success", "adapter-result-subtype-mismatch"),
        (not metadata.is_error, "adapter-result-error"),
        (metadata.terminal_reason == "completed", "adapter-terminal-state-mismatch"),
        (metadata.stop_reason in {"end_turn", "tool_use"}, "adapter-stop-reason-mismatch"),
        (1 <= metadata.num_turns <= _MAX_TURNS_WITH_ONE_STRUCTURED_REPAIR, "adapter-turn-bound"),
        (
            _is_sha256(metadata.structured_output_sha256),
            "adapter-structured-output-digest-invalid",
        ),
        (
            metadata.structured_output_sha256 == hashlib.sha256(encode_json(fragment)).hexdigest(),
            "adapter-structured-output-digest-mismatch",
        ),
        (metadata.prompt_size > 0, "adapter-prompt-empty"),
        (_is_sha256(metadata.prompt_sha256), "adapter-prompt-digest-invalid"),
        (metadata.response_size > 0, "adapter-response-empty"),
        (_is_sha256(metadata.response_sha256), "adapter-response-digest-invalid"),
        (metadata.input_tokens > 0, "adapter-input-token-count-invalid"),
        (metadata.output_tokens > 0, "adapter-output-token-count-invalid"),
        (0.0 <= metadata.total_cost_usd <= SLICE_PROFILE.max_cost_usd, "adapter-cost-invalid"),
        (
            0
            < metadata.duration_api_ms
            <= metadata.duration_ms
            <= metadata.elapsed_ms
            <= _ACCEPTED_EXECUTION_CONFIG.api_timeout_ms,
            "adapter-duration-invalid",
        ),
        (metadata.environment_names == receipt.runtime.environment_names, "adapter-env-mismatch"),
        (
            metadata.claude_executable_sha256 == receipt.runtime.executable_sha256,
            "adapter-executable-mismatch",
        ),
    )
    reasons.extend(reason for accepted, reason in checks if not accepted)
    if metadata.parse_observation is not None:
        reasons.extend(
            f"adapter-{reason}"
            for reason in parse_observation_reasons(
                metadata.parse_observation,
                digest=metadata.parse_observation_sha256,
                response_sha256=metadata.response_sha256,
                response_size=metadata.response_size,
            )
        )
        if metadata.parse_observation.status not in {
            "accepted-object",
            "accepted-result-array",
        }:
            reasons.append("adapter-response-untyped")
    if len(metadata.model_usage) != 1:
        reasons.append("adapter-model-count-mismatch")
    else:
        model = metadata.model_usage[0]
        if (model.model, model.canonical_model, model.provider) != (
            _CLAUDE_MODEL,
            _CLAUDE_CANONICAL_MODEL,
            _CLAUDE_PROVIDER,
        ):
            reasons.append("adapter-model-identity-mismatch")
        if (
            min(
                model.input_tokens,
                model.output_tokens,
                model.cache_read_input_tokens,
                model.cache_creation_input_tokens,
            )
            < 0
        ):
            reasons.append("adapter-model-token-count-invalid")
        if (metadata.input_tokens, metadata.output_tokens) != (
            model.input_tokens,
            model.output_tokens,
        ):
            reasons.append("adapter-token-count-mismatch")
    argv = metadata.argv
    schema = recorded_schema(argv, SLICE_PROFILE)
    if argv != expected_adapter_argv(SLICE_PROFILE, schema):
        reasons.append("adapter-argv-shape-mismatch")
    if hashlib.sha256(schema.encode()).hexdigest() != GRAPHIFY_SCHEMA_SHA256:
        reasons.append("adapter-schema-digest-mismatch")
    return reasons


def _runtime_reasons(runtime: ClaudePreflight, *, enforce_authority: bool) -> list[str]:
    # The version half is DERIVED from the runtime half, never restated beside
    # it. That is the fix for a defect this site carried twice.
    #
    # The pair exists to catch CLI/SDK SKEW: `graphify_runtime` is the installed
    # runtime identity and `graphify_version` is what the SDK reports, derived
    # separately, and a run where they disagree is one nobody reviewed. What the
    # pair must NOT do is police the two halves of an ACCEPTED entry against each
    # other — an accepted runtime's own version is not a second opinion about
    # itself, it is the same fact written twice, and a fact written twice drifts.
    #
    # It drifted. The 0.9.46 -> 0.9.47 bump advanced `_CURRENT_GRAPHIFY_RUNTIME`
    # and left its literal at "0.9.46", so this tuple became unmatchable and the
    # non-authority path rejected EVERY run under the installed version — with
    # both `receipt-runtime-mismatch` and `receipt-graphify-version-mismatch`.
    # The comment that used to sit here predicted precisely that ("a literal left
    # beside a newer runtime makes the pair unmatchable"), having been written
    # after the same thing happened at 0.9.46 — and the prediction did not
    # prevent the recurrence, because prose cannot. Deriving it can.
    #
    # The two entries still DIVERGE by design, which is the reason there are two:
    # the AUTHORITY pair stays at the version where the committed slice evidence
    # was produced and never advances on a pin bump alone (that would assert an
    # identity the receipt on disk contradicts), while the CURRENT pair moves
    # with the pin. They converge only when the slice re-runs and commits a new
    # receipt under the installed version.
    accepted_graphify_runtimes_for_path = (
        (_ACCEPTED_GRAPHIFY_RUNTIME,)
        if enforce_authority
        else (_ACCEPTED_GRAPHIFY_RUNTIME, _CURRENT_GRAPHIFY_RUNTIME)
    )
    accepted_graphify_pairs = tuple(
        (identity, identity.version) for identity in accepted_graphify_runtimes_for_path
    )
    accepted_graphify_runtimes = tuple(pair[0] for pair in accepted_graphify_pairs)
    names = set(runtime.environment_names)
    allowed = {*_CHILD_BASE_ENV_NAMES, *_CHILD_CONTROL_ENV}
    required = {*_CHILD_CONTROL_ENV, "PATH"}
    checks = (
        (runtime.executable == "claude", "receipt-claude-executable-name-mismatch"),
        (runtime.version == _ACCEPTED_CLAUDE_VERSION, "receipt-claude-version-mismatch"),
        (
            runtime.executable_sha256 == _ACCEPTED_CLAUDE_EXECUTABLE_SHA256,
            "receipt-claude-executable-digest-mismatch",
        ),
        (runtime.help_sha256 == _ACCEPTED_CLAUDE_HELP_SHA256, "receipt-claude-help-mismatch"),
        # `--max-turns` is proven by the preflight (`require_max_turns=True`) and
        # therefore appears in the receipt's flag list, so the expectation carries
        # it too. Comparing against the bare tuple would fail every real run.
        (
            runtime.required_flags == (*_REQUIRED_CLAUDE_FLAGS, "--max-turns"),
            "receipt-cli-flags-mismatch",
        ),
        (
            runtime.graphify_runtime in accepted_graphify_runtimes,
            "receipt-runtime-mismatch",
        ),
        (
            (runtime.graphify_runtime, runtime.graphify_version) in accepted_graphify_pairs,
            "receipt-graphify-version-mismatch",
        ),
        (
            runtime.graphify_semantic_fingerprint_sha256 == _ACCEPTED_SEMANTIC_FINGERPRINT_SHA256,
            "receipt-semantic-fingerprint-mismatch",
        ),
        (names <= allowed, "receipt-runtime-env-name-invalid"),
        (required <= names, "receipt-runtime-control-missing"),
    )
    return [reason for accepted, reason in checks if not accepted]


def _chunk_reasons(receipt: SemanticReceipt, metadata: object, fragment: object) -> list[str]:
    from kb_setup.graphify_semantic_adapter import AdapterMetadata

    if not isinstance(metadata, AdapterMetadata) or not isinstance(fragment, dict):
        return ["chunk-evidence-unavailable"]
    counts = _fragment_counts(fragment)
    expected = ChunkEvidence(
        ordinal=1,
        total=1,
        source_path=SOURCE_PATH,
        source_git_object=SOURCE_GIT_OBJECT,
        source_sha256=SOURCE_SHA256,
        source_size=SOURCE_SIZE,
        prompt_sha256=metadata.prompt_sha256,
        fragment_sha256=metadata.structured_output_sha256,
        node_count=counts[0],
        edge_count=counts[1],
        hyperedge_count=counts[2],
    )
    return [] if receipt.chunks == (expected,) else ["chunk-ledger-mismatch"]


def _receipt_reasons(
    receipt: SemanticReceipt,
    manifest: CandidateManifest,
    payloads: Mapping[str, bytes],
    fragment: object,
    *,
    enforce_authority: bool,
) -> list[str]:
    metadata_raw = payloads["adapter-metadata.json"]
    fragment_raw = payloads["semantic-fragment.json"]
    reasons: list[str] = []
    checks = (
        (receipt.schema_id == _CANDIDATE_SCHEMA, "receipt-schema-mismatch"),
        (receipt.status == "complete", "receipt-incomplete"),
        (receipt.source == expected_source_identity(), "receipt-source-identity-mismatch"),
        (receipt.source == manifest.source, "receipt-manifest-source-mismatch"),
        (
            receipt.runtime.auth
            == AuthIdentity(
                logged_in=True,
                auth_method="claude.ai",
                api_provider=_CLAUDE_PROVIDER,
                subscription_type="max",
            ),
            "receipt-auth-mismatch",
        ),
        (receipt.attempts == 1, "receipt-attempt-mismatch"),
        (receipt.backend == "claude-cli", "receipt-backend-mismatch"),
        (receipt.model == _CLAUDE_MODEL, "receipt-model-mismatch"),
        (receipt.max_concurrency == 1, "receipt-concurrency-mismatch"),
        (receipt.max_retry_depth == 0, "receipt-retry-depth-mismatch"),
        (
            receipt.execution_config == _ACCEPTED_EXECUTION_CONFIG,
            "receipt-execution-config-mismatch",
        ),
        (receipt.failed_chunks == 0, "receipt-failed-chunks"),
        (receipt.uncovered_files == (), "receipt-uncovered-files"),
        (receipt.out_of_scope_dropped == 0, "receipt-out-of-scope-dropped"),
        (receipt.warnings == (), "receipt-warning-bearing"),
        (receipt.errors == (), "receipt-error-bearing"),
        (
            receipt.adapter_metadata_sha256 == hashlib.sha256(metadata_raw).hexdigest(),
            "receipt-adapter-digest-mismatch",
        ),
        (
            receipt.semantic_fragment_sha256 == hashlib.sha256(fragment_raw).hexdigest(),
            "receipt-fragment-digest-mismatch",
        ),
    )
    reasons.extend(reason for accepted, reason in checks if not accepted)
    reasons.extend(_runtime_reasons(receipt.runtime, enforce_authority=enforce_authority))
    if isinstance(fragment, dict):
        counts = (
            len(fragment.get("nodes", [])),
            len(fragment.get("edges", [])),
            len(fragment.get("hyperedges", [])),
        )
        if counts != (
            receipt.semantic_node_count,
            receipt.semantic_edge_count,
            receipt.semantic_hyperedge_count,
        ):
            reasons.append("receipt-semantic-count-mismatch")
    if receipt.graph_node_count < receipt.semantic_node_count:
        reasons.append("receipt-graph-node-count-invalid")
    if receipt.graph_edge_count < receipt.semantic_edge_count:
        reasons.append("receipt-graph-edge-count-invalid")
    return reasons


def _verify_candidate(candidate: Path, *, enforce_authority: bool) -> SemanticVerification:
    reasons = _candidate_entry_reasons(candidate)
    if reasons:
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=tuple(reasons),
        )
    try:
        manifest_raw = (candidate / "manifest.json").read_bytes()
        manifest = msgspec.json.decode(manifest_raw, type=CandidateManifest, strict=True)
    except OSError, msgspec.DecodeError:
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=("manifest-corrupt",),
        )
    if not isinstance(manifest, CandidateManifest):
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=("manifest-schema-mismatch",),
        )
    reasons.extend(_manifest_reasons(manifest))
    if (
        enforce_authority
        and hashlib.sha256(manifest_raw).hexdigest() != _ACCEPTED_CANDIDATE_MANIFEST_SHA256
    ):
        reasons.append("candidate-authority-mismatch")
    if reasons:
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    member_reasons, payloads = _member_reasons(candidate, manifest)
    reasons.extend(member_reasons)
    if reasons:
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    try:
        receipt = msgspec.json.decode(payloads["receipt.json"], type=SemanticReceipt, strict=True)
        from kb_setup.graphify_semantic_adapter import AdapterMetadata

        metadata = msgspec.json.decode(
            payloads["adapter-metadata.json"], type=AdapterMetadata, strict=True
        )
        fragment = msgspec.json.decode(payloads["semantic-fragment.json"], strict=True)
    except KeyError, msgspec.DecodeError:
        reasons.append("member-schema-mismatch")
    else:
        fragment_failures = fragment_reasons(fragment, source_path=SOURCE_PATH)
        reasons.extend(fragment_failures)
        if not fragment_failures:
            reasons.extend(_adapter_reasons(metadata, receipt, fragment))
            reasons.extend(_chunk_reasons(receipt, metadata, fragment))
            reasons.extend(
                _receipt_reasons(
                    receipt,
                    manifest,
                    payloads,
                    fragment,
                    enforce_authority=enforce_authority,
                )
            )
    unique = tuple(dict.fromkeys(reasons))
    return SemanticVerification(
        state="failed" if unique else ("complete" if enforce_authority else "unapproved"),
        structural_complete=not unique,
        real_semantic_complete=enforce_authority and not unique,
        reasons=unique,
    )


def verify_candidate(candidate: Path) -> SemanticVerification:
    """Independently verify a candidate against the reviewed real-run authority."""
    return _verify_candidate(candidate, enforce_authority=True)


@contextmanager
def _temporary_environment(updates: Mapping[str, str]) -> Generator[None]:
    prior = {name: os.environ.get(name) for name in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for name, value in prior.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _write_json(path: Path, value: object) -> bytes:
    raw = encode_json(value) + b"\n"
    path.write_bytes(raw)
    return raw


def _admit_source(repo_root: Path, destination: Path) -> tuple[Path, object]:
    from kb_setup import graph, graphify_baseline

    source_manifest = graphify_baseline.historical_graphify_manifest(
        repo_root,
        ref=SOURCE_REF,
        commit=SOURCE_COMMIT,
    )
    provenance = graph.materialize_source_snapshot(source_manifest, destination)
    if (source_manifest.ref, provenance.resolved_commit, provenance.tree_digest) != (
        SOURCE_REF,
        SOURCE_COMMIT,
        SOURCE_TREE,
    ):
        raise ValueError("Graphify semantic source identity drifted")
    inventory = graphify_baseline.source_manifest(
        destination,
        commit=SOURCE_COMMIT,
        tree=SOURCE_TREE,
    )
    matches = tuple(member for member in inventory.members if member.path == SOURCE_PATH)
    if len(matches) != 1:
        raise ValueError("Graphify semantic source member is unavailable")
    member = matches[0]
    if (member.git_object, member.sha256, member.size) != (
        SOURCE_GIT_OBJECT,
        SOURCE_SHA256,
        SOURCE_SIZE,
    ):
        raise ValueError("Graphify semantic source bytes drifted")
    return destination / SOURCE_PATH, inventory


def admit_source(repo_root: Path, destination: Path) -> tuple[Path, object]:
    """Materialize and verify the complete pinned Graphify source snapshot."""
    return _admit_source(repo_root, destination)


def normalize_fragment(result: object) -> dict[str, object]:
    """Reduce one raw provider result to a fragment, WITHOUT checking its scope.

    Split out for the corpus driver, and the split is the substance of a cold-lane
    finding. The scope assertion below was hardcoded to the slice's single
    ``SOURCE_PATH``, so a corpus chunk citing any other file raised — after its
    provider call was already paid for.

    Scoping is not merely parameterised out, it is moved: the corpus's authority
    for that question is ``stage_chunk``, which produces REASONS for one chunk.
    Raising here instead would abort the entire extraction on a single chunk the
    model under-covered, turning one refused chunk into a lost corpus.
    """
    if not isinstance(result, dict):
        raise TypeError("Graphify semantic result is not an object")
    fragment: dict[str, object] = {}
    for field in ("nodes", "edges", "hyperedges"):
        records = _records(result.get(field, []))
        if records is None:
            raise TypeError(f"Graphify semantic {field} are invalid")
        exact: list[dict[str, object]] = []
        for record in records:
            if record.get("_origin") not in (None, "semantic"):
                raise ValueError(f"Graphify semantic {field} origin drifted")
            exact.append(record)
        fragment[field] = exact
    return fragment


def semantic_fragment(
    result: object, *, source_paths: tuple[str, ...] = (SOURCE_PATH,)
) -> dict[str, object]:
    """Normalize one result and ASSERT it is scoped to ``source_paths``.

    The slice's behaviour, unchanged: exactly one source, and anything outside it
    is a hard failure of a run that was supposed to touch one document.
    """
    fragment = normalize_fragment(result)
    reasons = fragment_scope_reasons(fragment, source_paths=source_paths)
    if reasons:
        raise ValueError("Graphify semantic fragment failed: " + ", ".join(reasons))
    return fragment


_semantic_fragment = semantic_fragment


def _fragment_counts(fragment: Mapping[str, object]) -> tuple[int, int, int]:
    counts: list[int] = []
    for field in ("nodes", "edges", "hyperedges"):
        records = _records(fragment.get(field))
        if records is None:
            raise TypeError(f"Graphify semantic {field} are invalid")
        counts.append(len(records))
    return counts[0], counts[1], counts[2]


def _adapter_environment(
    *,
    preflight_receipt: ClaudePreflight,
    metadata_path: Path,
    adapter_dir: Path,
    boundary_path: Path,
    profile: ClaudeProfile = SLICE_PROFILE,
) -> dict[str, str]:
    original_path = os.environ.get("PATH", "")
    entrypoint = shutil.which("kb-semantic-claude", path=original_path)
    if entrypoint is None:
        raise ValueError("KB semantic Claude adapter entrypoint is unavailable")
    real_claude = shutil.which("claude", path=original_path)
    if real_claude is None:
        raise ValueError("Claude Code CLI is unavailable")
    real_path = Path(real_claude).resolve()
    if sha256_file(real_path) != preflight_receipt.executable_sha256:
        raise ValueError("Claude Code executable changed after preflight")
    (adapter_dir / "claude").symlink_to(Path(entrypoint).resolve())
    return {
        "PATH": f"{adapter_dir}{os.pathsep}{original_path}",
        "KB_SEMANTIC_REAL_CLAUDE": str(real_path),
        "KB_SEMANTIC_REAL_CLAUDE_SHA256": preflight_receipt.executable_sha256,
        "KB_SEMANTIC_ORIGINAL_PATH": original_path,
        "KB_SEMANTIC_METADATA_PATH": str(metadata_path),
        # ONE adapter contract, both callers. graphify #309 made the provider
        # boundary marker mandatory in `graphify_semantic_adapter.adapter_main`
        # and migrated only the corpus launcher, so this path has failed with
        # `provider boundary marker path is unset` ever since — undetected,
        # because `verify` reads the artifacts #308 had already committed. A
        # generator that no longer runs, behind a verifier reading yesterday's
        # output.
        #
        # Deliberately NOT fixed by making the marker optional: nothing checks
        # after the fact that it was written, so "absent means skip" would let a
        # corpus run that merely FORGOT the variable lose its boundary evidence
        # in silence. Setting it here keeps the adapter fail-closed for everyone
        # and gives the slice the provider-call evidence it never had.
        "KB_SEMANTIC_PROVIDER_BOUNDARY_PATH": str(boundary_path),
        # Named explicitly even though the slice is the fail-closed default: a
        # launcher that relies on the default is indistinguishable from one that
        # forgot, and the adapter's rejection message should be able to say which.
        PROFILE_ENV_NAME: profile.name,
        "GRAPHIFY_CLAUDE_CLI_MODEL": profile.model,
        "GRAPHIFY_API_TIMEOUT": "120",
        "GRAPHIFY_NO_INCREMENTAL_CACHE": "1",
    }


def _extract_real_semantic(
    source: Path,
    *,
    root: Path,
    cache_root: Path,
    environment: Mapping[str, str],
) -> tuple[
    dict[str, object],
    tuple[str, ...],
    tuple[tuple[int, int, str, tuple[int, int, int]], ...],
]:
    from kb_setup import graphify_sdk

    stream = io.StringIO()
    observed_chunks: list[tuple[int, int, str, tuple[int, int, int]]] = []

    def observe_chunk(index: int, total: int, raw: object) -> None:
        fragment = _semantic_fragment(raw)
        observed_chunks.append(
            (
                index + 1,
                total,
                hashlib.sha256(encode_json(fragment)).hexdigest(),
                _fragment_counts(fragment),
            )
        )

    with (
        _temporary_environment(environment),
        warnings.catch_warnings(record=True) as caught,
        redirect_stderr(stream),
    ):
        warnings.simplefilter("always")
        result = graphify_sdk.extract_corpus_parallel(
            [source],
            backend="claude-cli",
            model=_CLAUDE_MODEL,
            root=root,
            chunk_size=1,
            token_budget=None,
            max_concurrency=1,
            max_retry_depth=0,
            on_chunk_done=observe_chunk,
            deep_mode=False,
            cache_root=cache_root,
        )
    warning_text = tuple(
        item
        for item in (stream.getvalue().strip(), *(str(warning.message) for warning in caught))
        if item
    )
    return result, warning_text, tuple(observed_chunks)


def result_integer(result: Mapping[str, object], name: str) -> int:
    """Read one integer counter from a raw extraction result, or -1 if absent.

    -1 rather than 0 on purpose, and public for the corpus driver: 0 is a real,
    meaningful answer for `failed_chunks`, so a missing key and a clean run must
    not reduce to the same number.
    """
    value = result.get(name)
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


_result_integer = result_integer


def _coverage_evidence(result: Mapping[str, object]) -> tuple[int, tuple[str, ...], int]:
    failed_chunks = _result_integer(result, "failed_chunks")
    dropped = _result_integer(result, "out_of_scope_dropped")
    uncovered_value = result.get("uncovered_files")
    if not isinstance(uncovered_value, list) or not all(
        isinstance(item, str) for item in uncovered_value
    ):
        raise ValueError("Graphify semantic uncovered-file evidence is invalid")
    uncovered = tuple(uncovered_value)
    if failed_chunks != 0 or uncovered or dropped != 0:
        raise ValueError("Graphify semantic extraction was partial")
    if result.get("_partial_files") not in (None, []):
        raise ValueError("Graphify semantic extraction reported partial files")
    return failed_chunks, uncovered, dropped


def build_candidate(repo_root: Path, output: Path) -> CandidateManifest:
    """Run exactly one real semantic call and atomically publish verified evidence."""
    from kb_setup import graphify_baseline, graphify_sdk
    from kb_setup.graphify_semantic_adapter import AdapterMetadata

    # Scrubbed here too, even though `semantic_main` already scrubs before
    # dispatching to this function: `build_candidate` is public and may be
    # called directly, bypassing that entry point (#334). `report_routing_scrub`
    # is what makes a run that had to remove something distinguishable, after
    # the fact, from one that never had anything to remove — the two used to
    # be byte-indistinguishable (cold review P1-1).
    report_routing_scrub("build_candidate", scrub_route_overrides())
    if output.exists():
        raise ValueError(f"semantic output already exists: {output}")
    # `require_max_turns` follows the boundary marker: the adapter adds
    # `--max-turns 3` exactly when `KB_SEMANTIC_PROVIDER_BOUNDARY_PATH` is set,
    # so the flag must be PROVEN supported in the same run that will pass it.
    preflight_receipt = preflight(repo_root, require_max_turns=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kb-graphify-semantic-source-") as source_dir:
        source_root = Path(source_dir) / "graphify"
        source_path, before = _admit_source(repo_root, source_root)
        with (
            tempfile.TemporaryDirectory(prefix="kb-graphify-semantic-cache-") as cache_dir,
            tempfile.TemporaryDirectory(prefix="kb-graphify-semantic-adapter-") as bin_dir,
            tempfile.TemporaryDirectory(
                prefix=f".{output.name}-", dir=output.parent
            ) as candidate_dir,
        ):
            candidate = Path(candidate_dir)
            metadata_path = candidate / "adapter-metadata.json"
            environment = _adapter_environment(
                preflight_receipt=preflight_receipt,
                metadata_path=metadata_path,
                adapter_dir=Path(bin_dir),
                boundary_path=candidate / _PROVIDER_BOUNDARY_MEMBER,
            )
            result, warning_text, observed_chunks = _extract_real_semantic(
                source_path,
                root=source_root,
                cache_root=Path(cache_dir),
                environment=environment,
            )
            after = graphify_baseline.source_manifest(
                source_root,
                commit=SOURCE_COMMIT,
                tree=SOURCE_TREE,
            )
            if after != before:
                raise ValueError("source-snapshot-drift: semantic input changed")
            if warning_text:
                raise ValueError("Graphify semantic warnings: " + "; ".join(warning_text))
            failed_chunks, uncovered, dropped = _coverage_evidence(result)
            fragment = _semantic_fragment(result)
            built_graph, build_receipt = graphify_sdk.build_checked([fragment], root=source_root)
            if build_receipt.stderr or build_receipt.reasons:
                raise ValueError("Graphify semantic build was warning-bearing")
            try:
                metadata_raw = metadata_path.read_bytes()
                metadata = msgspec.json.decode(metadata_raw, type=AdapterMetadata, strict=True)
            except (OSError, msgspec.DecodeError) as exc:
                raise ValueError("semantic adapter metadata is unavailable") from exc
            fragment_raw = _write_json(candidate / "semantic-fragment.json", fragment)
            counts = _fragment_counts(fragment)
            expected_observed = (
                (
                    1,
                    1,
                    metadata.structured_output_sha256,
                    counts,
                ),
            )
            if observed_chunks != expected_observed:
                raise ValueError("Graphify semantic chunk callback evidence drifted")
            chunks = (
                ChunkEvidence(
                    ordinal=1,
                    total=1,
                    source_path=SOURCE_PATH,
                    source_git_object=SOURCE_GIT_OBJECT,
                    source_sha256=SOURCE_SHA256,
                    source_size=SOURCE_SIZE,
                    prompt_sha256=metadata.prompt_sha256,
                    fragment_sha256=metadata.structured_output_sha256,
                    node_count=counts[0],
                    edge_count=counts[1],
                    hyperedge_count=counts[2],
                ),
            )
            receipt = SemanticReceipt(
                schema_id=_CANDIDATE_SCHEMA,
                status="complete",
                source=expected_source_identity(),
                runtime=preflight_receipt,
                adapter_metadata_sha256=hashlib.sha256(metadata_raw).hexdigest(),
                semantic_fragment_sha256=hashlib.sha256(fragment_raw).hexdigest(),
                chunks=chunks,
                execution_config=_ACCEPTED_EXECUTION_CONFIG,
                attempts=metadata.attempt,
                backend="claude-cli",
                model=_CLAUDE_MODEL,
                max_concurrency=1,
                max_retry_depth=0,
                failed_chunks=failed_chunks,
                uncovered_files=uncovered,
                out_of_scope_dropped=dropped,
                semantic_node_count=counts[0],
                semantic_edge_count=counts[1],
                semantic_hyperedge_count=counts[2],
                graph_node_count=int(built_graph.number_of_nodes()),
                graph_edge_count=int(built_graph.number_of_edges()),
                warnings=(),
                errors=(),
            )
            _write_json(candidate / "receipt.json", receipt)
            members = tuple(
                ArtifactMember(
                    name=name,
                    sha256=sha256_file(candidate / name),
                    size=(candidate / name).stat().st_size,
                )
                for name in sorted(_REQUIRED_MEMBERS)
            )
            manifest = CandidateManifest(
                schema_id=_CANDIDATE_SCHEMA,
                source=expected_source_identity(),
                members=members,
                warnings=(),
            )
            _write_json(candidate / "manifest.json", manifest)
            verification = _verify_candidate(candidate, enforce_authority=False)
            if not verification.structural_complete:
                raise ValueError(
                    "semantic candidate structural verification failed: "
                    + ", ".join(verification.reasons)
                )
            candidate.replace(output)
            return manifest


def semantic_main(repo_root: Path, args: list[str]) -> int:
    """Preflight, build, or independently verify the #300 semantic slice."""
    # Scrub before ANY dispatch, including a usage error: `preflight` (called
    # directly below) and `build_candidate` (which preflights internally) must
    # never see a forbidden routing name that this process could have removed
    # itself (#334) — see `scrub_route_overrides`. Reported through
    # `report_routing_scrub` (cold review P1-1); when this one already found
    # and removed everything, `build_candidate`'s own scrub below is
    # idempotent and reports nothing further.
    report_routing_scrub("semantic_main", scrub_route_overrides())
    if not args or args[0] not in {"preflight", "run", "verify"} or len(args) > _MAX_SEMANTIC_ARGS:
        print("kb-setup graphify-semantic-slice preflight|run|verify [PATH]")
        return 2
    command = args[0]
    if command == "preflight":
        if len(args) != 1:
            print("kb-setup graphify-semantic-slice preflight")
            return 2
        print(msgspec.json.encode(preflight(repo_root)).decode())
        return 0
    output = (
        Path(args[1])
        if len(args) == _MAX_SEMANTIC_ARGS
        else repo_root / "graphify-out/graphify-semantic-slice"
    )
    result = build_candidate(repo_root, output) if command == "run" else verify_candidate(output)
    print(msgspec.json.encode(result).decode())
    complete = (
        result.real_semantic_complete
        if isinstance(result, SemanticVerification)
        else verify_candidate(output).real_semantic_complete
    )
    return 0 if complete else 1
