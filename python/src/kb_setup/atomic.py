# Copyright (c) 2026 Raymond Manaloto
"""Temp-then-rename writes — never truncate a durable artifact in place.

`Path.write_text` truncates the destination first, so an interrupted write
leaves a half-written or empty file where a valid one used to be. For an
artifact whose whole job is to be read LATER — a scoring baseline, a gate record
— that is not a lost write, it is a corrupted one: the next reader either parses
garbage or (correctly) discards the file and silently loses everything it held.

Extracted from `kb_setup.skill_eval`, which had the only copy, when
`kb_setup.gates` needed the same guarantee (#146, cold review). This repo's rule
is that a module earns its place at **two or more callers**; a second copy of a
durability primitive is exactly the duplication that stays identical right up
until one of them is hardened and the other is not.
"""

from __future__ import annotations

import os
from pathlib import Path


def write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via a temp file and a rename, never in place.

    A rename is atomic on POSIX, so a reader sees either the old file or the new
    one and never a partial. The temp file is removed if the write fails, so a
    crashed run leaves no debris beside the real artifact.
    """
    # The pid is not decoration. A temp name derived ONLY from the destination
    # means two concurrent writers share one inode: one can rename the file out
    # from under the other (FileNotFoundError on the second `replace`), or both
    # can interleave bytes into it before either rename. Pre-existing in
    # `skill_eval`, and inherited unchanged by the extraction — but this module
    # now has a second caller whose concurrent case is plausible (two `kb-gates`
    # runs at one commit), so it is fixed here rather than carried forward.
    # (Cold lane round 2, P2, correctly labelled pre-existing.)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
