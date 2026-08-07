# Copyright (c) 2026 Raymond Manaloto
"""Shared currency-stamp refresh for any operation that rewrites graph.json wholesale.

THREE callers need the exact same best-effort behaviour: `artifacts.generate`
(after the `report` entry's `cluster-only` rewrite), `graphify_ops._labelled`
(after `graphify label`'s own `to_json` rewrite, #171/#175), and
`graphify_ops.merge_chunk` (after `_merge_docs.py` rewrites the graph, #181).
Each regenerates an artifact `currency.toml` fingerprints without changing WHO
built the underlying graph, so each needs to refresh
`graphify-out/.currency-stamp.json`'s fingerprint map or step 1 of
`kb-currency-check` reports every manual `kb-merge` / `kb-label` /
`kb-artifacts` run as build-stamp drift until the next full `kb-build` (#179).

This docstring said "two callers" for one release while the third was deferred
out of #179 — the count is repeated here rather than elided precisely so the
next omission is visible in a diff.

A single `refresh_after_regen` rather than two copies: a duplicated four-
exception-type best-effort block is precisely the kind of pair that drifts —
one gets a fix the other does not, silently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def snapshot_views(repo_root: Path) -> dict[str, dict[str, str]] | None:
    """`{tool: {view: identity}}` as they are RIGHT NOW, for `refresh_after_regen`.

    Take one BEFORE doing work that might regenerate a derived view, and hand it
    back afterwards. That bracket is what lets the stamp record which graph a view
    was generated from without any caller enumerating what it regenerated (#182).

    Returns None — meaning "no snapshot" rather than "nothing was there" — when
    the config cannot be read, so a broken `currency.toml` degrades to unknown
    provenance instead of certifying views against a bracket that was never taken.
    An empty dict is a real snapshot and is treated as one.
    """
    try:
        from kb_setup.currency import config, sync

        return {
            spec.name: sync.view_identities(repo_root, spec)
            for spec in config.load(repo_root)
            if spec.stamp
        }
    except OSError, ValueError, TypeError, ImportError:
        return None


def refresh_after_regen(
    repo_root: Path, *, tag: str, views_before: dict[str, dict[str, str]] | None = None
) -> None:
    """Refresh the currency stamp's fingerprints for a just-regenerated artifact.

    Without this, step 1 would report every generated output as "changed since
    stamped" the moment the caller ran — the outputs it just legitimately
    regenerated. Best-effort and version-preserving: regenerating a derived
    view does not change who built the graph, so a missing stamp (build not
    yet run) is left for `kb-build`, not invented here. A partial `only=` run
    (the `kb-artifacts` caller) still re-stamps the whole declared set, which
    is correct: the fingerprint map always reflects what is on disk now — and
    that includes files the caller did NOT just regenerate. A `kb-label` run,
    for instance, only rewrites `graphify-out/graph.json`, but
    `sync.restamp_artifacts` re-fingerprints `GRAPH_REPORT.md` / `graph.graphml`
    / `wiki` too, because the stamp answers "has anything moved since we last
    looked", not "is every output mutually consistent" — the same semantics
    already documented for a partial `kb-artifacts only=` run. That is
    deliberate, not a bug: re-observing `sources/` instead would be drift
    laundering (a derived-view regeneration has no standing to restate what the
    graph was built FROM), which is exactly what `restamp_artifacts` avoids by
    carrying the recorded input fingerprints forward verbatim rather than
    re-observing `sources/`.

    `tag` names the CALLER in every printed line, because this message is the
    only thing telling someone which of their commands touched the stamp —
    `[kb-artifacts]` after a `kb-label` run would send them looking at the
    wrong task.

    `views_before` is a `snapshot_views` result taken before the caller started
    working (#182). A view is certified against the current graph only when its
    identity changed inside that bracket — so a caller that regenerated views
    passes one, and a caller that only rewrote the graph passes nothing and its
    views are correctly reported as describing an earlier graph.

    Passing None is the safe default and means "I cannot say what I regenerated".
    It is NOT the same as passing an empty snapshot, which is a real observation
    that no view existed at the start.
    """
    try:
        from kb_setup.currency import config, sync

        for spec in config.load(repo_root):
            if not spec.stamp:
                continue
            before = None if views_before is None else views_before.get(spec.name, {})
            path = sync.restamp_artifacts(repo_root, spec, views_before=before)
            if path is not None:
                print(f"[{tag}] re-stamped {path.name} for {spec.name}")
    except (OSError, ValueError, TypeError, ImportError) as e:
        # TypeError too: config.load() raises it (not ValueError) when a
        # `[tool.*]` entry is not a proper table. A malformed currency.toml must
        # not turn an otherwise-successful caller into a hard failure — the
        # re-stamp is best-effort by design.
        print(f"[{tag}] WARNING: could not refresh the currency stamp: {e}")
