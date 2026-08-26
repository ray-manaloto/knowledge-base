"""Dynamically decorate real kb_setup functions from the OUTSIDE — no edits to
the knowledge-base repo tree. Chooses a real, pure call chain: result.exit_code
consults Ok/Err/Rc, mirroring the R5 typed-error-surface doc's own worked
example."""
import sequenceDiagram as sd
from sequenceDiagram import sequenceDiagram as seqdec, writehtml

from kb_setup.result import Err, Ok, Rc, exit_code

# Reassign the module-level names to sequenceDiagram-wrapped versions. This
# mutates only THIS script's process, never kb_setup's files on disk.
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

writehtml("kb_entrypoint.html")
print("traces:", len(sd.traces))
for t in sd.traces:
    print(" ", t)
