"""kb-setup CLI — minimal entrypoint (fleshed out as the KB grows)."""

from __future__ import annotations

import sys

from kb_setup import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in {"-V", "--version", "version"}:
        print(f"kb-setup {__version__}")
        return 0
    print("kb-setup: knowledge-base helpers. Try `mise run kb-query` / `kb-build`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
