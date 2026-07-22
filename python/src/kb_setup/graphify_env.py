"""Locate graphify's bundled interpreter.

graphify installs as a pipx tool with its OWN venv python (it can `import
graphify`); the KB repo's uv python cannot. Code that calls graphify's Python API
(e.g. build_merge) must run under this interpreter, not uv's.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _imports_graphify(py: Path) -> bool:
    try:
        return subprocess.run(
            [str(py), "-c", "import graphify"], capture_output=True, timeout=30
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def graphify_python(repo_root: Path | None = None) -> str:
    """Return a path to an interpreter that can ``import graphify``.

    Resolution order: the marker graphify writes (``graphify-out/.graphify_python``),
    then ``mise where pipx:graphifyy`` → ``**/bin/python``, then the ``graphify``
    binary's sibling. Raises if none can import graphify.
    """
    root = repo_root or Path.cwd()

    marker = root / "graphify-out" / ".graphify_python"
    if marker.is_file():
        cand = Path(marker.read_text(encoding="utf-8").strip())
        if cand.is_file() and _imports_graphify(cand):
            return str(cand)

    try:
        out = subprocess.run(
            ["mise", "where", "pipx:graphifyy"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        base = Path(out.stdout.strip())
        for cand in sorted(base.glob("**/bin/python")):
            if _imports_graphify(cand):
                return str(cand)
    except (OSError, subprocess.SubprocessError):
        pass

    exe = shutil.which("graphify")
    if exe:
        cand = Path(exe).resolve().parent / "python"
        if cand.is_file() and _imports_graphify(cand):
            return str(cand)

    raise RuntimeError(
        "could not locate graphify's bundled interpreter — is `graphify` installed "
        "(mise install)?"
    )


# Runtime deps some graphify outputs need that its packaging does NOT pull on
# Python 3.14. On 3.12 scipy arrives transitively via graspologic (the leiden
# extra); on 3.14 graspologic is skipped, so `export svg` (nx.spring_layout →
# scipy) breaks. We inject it idempotently. Maps import-name -> pip-spec.
_OUTPUT_DEPS: dict[str, str] = {"scipy": "scipy"}


def ensure_runtime_deps(repo_root: Path | None = None) -> list[str]:
    """Idempotently install output-only runtime deps missing from graphify's env.

    Returns the list of packages it installed (empty if all present). Safe to call
    before every artifact run — a no-op once satisfied.
    """
    py = graphify_python(repo_root)
    installed: list[str] = []
    for mod, spec in _OUTPUT_DEPS.items():
        if _imports(py, mod):
            continue
        print(f"[deps] graphify env missing {mod!r} — injecting {spec}")
        subprocess.run(
            ["uv", "pip", "install", "--python", py, spec], check=True, timeout=600
        )
        installed.append(spec)
    return installed


def _imports(py: str, module: str) -> bool:
    try:
        return subprocess.run(
            [py, "-c", f"import {module}"], capture_output=True, timeout=30
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
