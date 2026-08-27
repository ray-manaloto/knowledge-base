from sequenceDiagram import sequenceDiagram, writehtml


@sequenceDiagram
def function_a():
    print("Function A")


@sequenceDiagram
def function_b():
    function_a()
    print("Function B")


function_b()
writehtml("out.html")
