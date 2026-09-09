"""Fail fast on syntax that breaks older Python interpreters.

Backslashes inside an f-string *expression* are legal from Python 3.12 but a
SyntaxError on 3.11 and earlier. A 3.12 interpreter parses them happily, so
`compileall` on a modern dev machine will not catch it — this lint does, by
inspecting the source text directly.

Run before anything else in CI: a syntax error found here costs 2 seconds,
the same error found during the refresh costs a failed publish.
"""
import glob, os, re, sys, py_compile, tempfile

FSTRING = re.compile(r"""(?:f|rf|fr|F|RF|FR)(['"]{1,3})(?:\\.|(?!\1).)*?\1""", re.S)
EXPR = re.compile(r"\{([^{}]*)\}", re.S)


def check_fstring_backslashes(path):
    src = open(path, encoding="utf-8").read()
    problems = []
    for m in FSTRING.finditer(src):
        for expr in EXPR.findall(m.group(0)):
            if "\\" in expr:
                line = src[:m.start()].count("\n") + 1
                problems.append((line, m.group(0)[:80]))
    return problems


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    failed = False
    tmpdir = tempfile.mkdtemp()
    for path in sorted(glob.glob(os.path.join(here, "*.py"))):
        name = os.path.basename(path)
        try:
            py_compile.compile(path, doraise=True,
                               cfile=os.path.join(tmpdir, name + "c"))
        except py_compile.PyCompileError as exc:
            print(f"SYNTAX ERROR  {name}: {exc}")
            failed = True
            continue
        for line, snippet in check_fstring_backslashes(path):
            print(f"INCOMPATIBLE  {name}:{line}  backslash inside f-string expression "
                  f"(SyntaxError on Python < 3.12)\n              {snippet}")
            failed = True
    if failed:
        print("\nCompatibility lint FAILED. Use %-formatting or .format(), or hoist the "
              "escaped text into a variable outside the f-string.")
        return 1
    print("Compatibility lint OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
