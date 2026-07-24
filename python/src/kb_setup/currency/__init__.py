"""Tool-currency engine — the shared core both this repo and dotfiles run.

Six steps, in the order Ray specified (2026-07-23):

1. `sync`     — is the installed tool in sync with the pin, the source manifest,
                the built artifacts and the declared extras?
2. `upstream` — is there a newer version?
3. `upstream` — what do its release notes say, and does anything affect us?
4. `issues`   — have any tracked issues / local watch items moved?
5. `decide`   — what residual ambiguity must a human resolve (via AskUserQuestion,
                which only the model can call — never the hook)?
6. `report`   — a committed landing row + a detail page, so the process itself is
                reviewable and improvable over time.

The engine only produces facts and a verdict. The *judgment* — reading release
notes, answering the interview — stays with the skill that drives it, per
`.claude/rules/tool-currency-and-native-first.md` in dotfiles.

Nothing here imports graphify, `gh`, or any repo-specific path at import time:
the config (`currency.toml`) names what to check, so a second repo adopts the
engine by adding a config file, not by editing this package.
"""

from __future__ import annotations

from kb_setup.currency.config import CONFIG_NAME, ToolSpec, WatchItem, load
from kb_setup.currency.decide import Ambiguity, Verdict, decide
from kb_setup.currency.sync import SyncStatus, check_sync

__all__ = [
    "CONFIG_NAME",
    "Ambiguity",
    "SyncStatus",
    "ToolSpec",
    "Verdict",
    "WatchItem",
    "check_sync",
    "decide",
    "load",
]
