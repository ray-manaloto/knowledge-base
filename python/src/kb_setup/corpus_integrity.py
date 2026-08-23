# Copyright (c) 2026 Raymond Manaloto
"""Staged provider evidence still hashes to what its receipts recorded.

## Why this exists

`hk.pkl`'s `proseExclude` keeps every formatter and spell-checker off
`graphify-out/graphify-semantic-corpus-chunks/**`. That is a PREVENTIVE control,
and preventive controls regress silently: a new formatter step added without
`proseExclude`, a new corpus path nobody adds to the list, or a tool run outside
hk entirely. This module is the DETECTIVE half — it asks whether the bytes still
match, rather than trusting that nothing was allowed to touch them.

The gap it closes is measured, not hypothetical. On 2026-08-23, `typos
--write-changes` reached these paths before the exclusion existed and rewrote
three fragments: one word "corrected" twice in chunk 0002 (-2 bytes), one in
chunk 0005 (+1), and one further edit in chunk 0009 that has still not been
identified. The words are deliberately not spelled here — this repo's own
formatter reaches `python/` and would rewrite them into identities. Nothing
noticed until `kb-graphify-semantic-corpus-merge` refused, by which point the
only commit that ever added the files had added them already damaged, so git
held no clean copy to diff against. Two of the three were recoverable only
because their receipts made a digest-verified search possible; the third was
not recovered at all.

**A gate here would have fired the same day**, while the pre-edit bytes were
still on disk. `lint` was red in that window — but red on the SPELLING, which
reads as "fix the typo or exclude the path", not as "your evidence has been
altered". Naming the real failure is most of this module's value.

## What it checks, and why both receipts

Each staged chunk directory holds four files. `semantic-fragment.json` is the
provider's output; `receipt.json` and `provider-receipt.json` each independently
record its SHA-256, written by different code paths.

Checking BOTH is what makes a finding actionable rather than ambiguous. Three
distinct states come out of it:

- both receipts agree with each other and disagree with the file -> the FILE was
  altered, and the receipts are authoritative. This is the 2026-08-23 shape.
- the two receipts disagree with EACH OTHER -> a receipt was altered, or the two
  writers diverged. A different defect, and one a single-receipt check would
  have reported as an ordinary drift and sent someone hunting the wrong file.
- everything agrees -> nothing to say.

A single-receipt check cannot separate the first two, and "which side is
authoritative" is the whole question a reader has when this fires.

## Exit codes

`Rc.OK` clean, `Rc.FINDINGS` drift, and `Rc.NOT_RUN` when no chunk was examined
at all — never `OK`. A tree with no staged corpus is the normal case on most
clones, but "nothing to check" and "checked, all good" are different claims, and
this repo's standing rule is that a gate which never asked the question is not a
pass (`probes-need-a-control-arm.md`). The caller decides whether NOT_RUN is
acceptable; `hk` treats only `FINDINGS` as a failure.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import msgspec

from kb_setup.result import Rc

#: Where staged provider evidence lives, relative to the repo root. A tuple
#: rather than one path because the retained-evidence tree and any future
#: staging root are the same KIND of thing, and the failure this module exists
#: to catch is precisely a new path nobody added to a list.
CORPUS_ROOTS: tuple[str, ...] = ("graphify-out/graphify-semantic-corpus-chunks",)

#: The provider output, and the two independent digests over it. The field names
#: differ between the receipts because the two writers named them differently;
#: that divergence is upstream's, and mirroring it here beats normalising it,
#: because a rename on either side should break this loudly rather than silently
#: read a missing key as absent-and-fine.
_FRAGMENT = "semantic-fragment.json"
_RECEIPTS: tuple[tuple[str, str], ...] = (
    ("receipt.json", "fragment_sha256"),
    ("provider-receipt.json", "semantic_fragment_sha256"),
)
_SIZE_FIELD = ("receipt.json", "fragment_size")


class Finding(msgspec.Struct, frozen=True):
    """One chunk that does not agree with its own receipts."""

    chunk: str
    """Repo-relative path of the chunk directory."""

    kind: str
    """`fragment-altered`, `receipts-disagree`, or `unreadable`."""

    detail: str
    """One line a reader can act on without opening anything."""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_field(chunk: Path, filename: str, field: str) -> object | None:
    """Return one field of one receipt, or None if it cannot be read.

    Deliberately forgiving about the file being ABSENT and strict about it being
    malformed: a chunk mid-write has no receipt yet, while a receipt that exists
    and will not parse is itself the finding.
    """
    path = chunk / filename
    if not path.is_file():
        return None
    return json.loads(path.read_text()).get(field)


def _chunk_findings(chunk: Path, rel: str) -> list[Finding]:
    fragment = chunk / _FRAGMENT
    if not fragment.is_file():
        return []
    raw = fragment.read_bytes()
    actual = _digest(raw)

    recorded: dict[str, str] = {}
    for filename, field in _RECEIPTS:
        try:
            value = _read_field(chunk, filename, field)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return [Finding(rel, "unreadable", f"{filename} does not parse: {exc}")]
        if isinstance(value, str):
            recorded[filename] = value

    if not recorded:
        return []

    distinct = set(recorded.values())
    if len(distinct) > 1:
        pairs = ", ".join(f"{name}={value[:12]}" for name, value in sorted(recorded.items()))
        return [
            Finding(
                rel,
                "receipts-disagree",
                f"the two receipts record different digests ({pairs}) — a RECEIPT was "
                "altered, or the two writers diverged; the fragment is not implicated",
            )
        ]

    expected = distinct.pop()
    if actual == expected:
        return []

    size = _read_field(chunk, *_SIZE_FIELD)
    drift = f", size {len(raw) - size:+d} bytes" if isinstance(size, int) else ""
    return [
        Finding(
            rel,
            "fragment-altered",
            f"{_FRAGMENT} hashes to {actual[:12]} but every receipt records "
            f"{expected[:12]}{drift} — the receipts agree with each other, so the "
            "FILE was altered after staging; do not re-stamp the receipts",
        )
    ]


def scan(repo_root: Path, roots: tuple[str, ...] = CORPUS_ROOTS) -> tuple[list[Finding], int]:
    """Walk every staged chunk under `roots`; return findings and how many were EXAMINED.

    The count is returned rather than inferred from the findings list because it
    is the only thing that separates "clean" from "never asked" at the callsite,
    and conflating those is how a gate reports green over an empty tree.
    """
    findings: list[Finding] = []
    examined = 0
    for root in roots:
        base = repo_root / root
        if not base.is_dir():
            continue
        for chunk in sorted(base.glob("*/chunks/*")):
            if not chunk.is_dir() or not (chunk / _FRAGMENT).is_file():
                continue
            examined += 1
            findings.extend(_chunk_findings(chunk, str(chunk.relative_to(repo_root))))
    return findings, examined


def render(findings: list[Finding], examined: int) -> str:
    """One block a reader can act on: the count, each drift, and the remedy."""
    if not examined:
        return (
            "[corpus-integrity] NOT RUN — no staged corpus chunk was examined under "
            + ", ".join(CORPUS_ROOTS)
            + ". This is not a pass: it means the question was never asked."
        )
    if not findings:
        return f"[corpus-integrity] {examined} staged chunk(s) match their receipts"
    lines = [f"[corpus-integrity] {len(findings)} of {examined} staged chunk(s) DRIFTED:"]
    lines += [f"  {f.chunk}: {f.kind} — {f.detail}" for f in findings]
    lines.append(
        "  Provider evidence is not regenerable at these digests. Restore the bytes "
        "(a candidate whose sha256 matches the receipt IS the original), never "
        "re-stamp the receipt to match the file."
    )
    return "\n".join(lines)


def integrity_main(repo_root: Path, argv: list[str] | None = None) -> int:
    """`uv run kb-setup corpus-integrity` — the seam `hk` and `kb-gates` call.

    Takes no arguments. An unrecognised one is `Rc.BAD_REQUEST`, not a silent
    ignore: a caller who passed a flag expecting it to narrow the scan would
    otherwise read a whole-tree result as the scoped one they asked for.
    """
    if argv:
        print(f"[corpus-integrity] takes no arguments; got {' '.join(argv)}")
        return Rc.BAD_REQUEST
    findings, examined = scan(repo_root)
    print(render(findings, examined))
    if not examined:
        return Rc.NOT_RUN
    return Rc.FINDINGS if findings else Rc.OK
