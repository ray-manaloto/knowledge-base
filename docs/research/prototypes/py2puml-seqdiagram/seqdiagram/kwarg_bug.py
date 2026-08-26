import sequenceDiagram as sd
from sequenceDiagram import sequenceDiagram as seqdec


@seqdec
def greet(name="world"):
    return f"hello {name}"


greet(name="ray")
for t in sd.traces:
    print(t)
