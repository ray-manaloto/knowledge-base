"""Same as kb_entrypoint_diagram.py, but with the one-line upstream bug
monkeypatched at runtime (proves fix size without touching the installed
package or the knowledge-base repo)."""
import sequenceDiagram as sd
from sequenceDiagram import sequenceDiagram as seqdec, writehtml, isiter, removechars

from kb_setup.result import Err, Ok, Rc, exit_code


def transformInput_fixed(args):
    """Upstream bug: appends the raw int/float/bool instead of str(a), which
    crashes ", ".join(...) the moment any numeric/bool argument is passed.
    One-line fix: str(a) instead of a."""
    listre = []
    if not (isiter(args)):
        args = [args]
    for a in args:
        if isinstance(a, int) or isinstance(a, float) or isinstance(a, bool):
            listre.append(str(a))  # <-- the one-line fix
        elif isinstance(a, str):
            if len(a) > 10:
                a = removechars(a)
                a = a[:10]
            listre.append(a)
        elif isinstance(a, object):
            listre.append(removechars(str(a.__class__.__name__)))
    listre = [element for element in listre if element is not None]
    return listre


sd.transformInput = transformInput_fixed

exit_code = seqdec(exit_code)


def build_and_report(ok: bool) -> int:
    if ok:
        result = Ok(42)
    else:
        result = Err("boom", rc=Rc.BAD_REQUEST)
    return exit_code(result)


build_and_report = seqdec(build_and_report)

print("rc(ok)=", build_and_report(True))
print("rc(err)=", build_and_report(False))

writehtml("kb_entrypoint_fixed.html")
print("traces:")
for t in sd.traces:
    print(" ", t)
