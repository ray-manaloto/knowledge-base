from sequenceDiagram import sequenceDiagram, writehtml, resetseq
import sequenceDiagram as sd


@sequenceDiagram
def f():
    pass


f()
print("traces after 1 call:", len(sd.traces))
resetseq()
print("traces after resetseq():", len(sd.traces))
f()
f()
print("traces after 2 more calls:", len(sd.traces))
