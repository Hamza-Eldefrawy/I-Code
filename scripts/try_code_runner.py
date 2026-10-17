import os
from src.code_runner import run_code, format_result, extract_code
from src.orchestrator import Orchestrator

os.environ["OPENROUTER_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "dummy-for-test")

CASES = {
    "success":      "print('hello'); print(2 + 2)",
    "runtime error": "print(1 / 0)",
    "syntax error": "def f(:\n    pass",
    "infinite loop": "while True:\n    pass",
    "input()":      "name = input('Name? ')\nprint(name)",
    "env leak":     "import os\nprint('KEY visible:', 'OPENROUTER_API_KEY' in os.environ)",
    "big output":   "print('x' * 20000)",
}

for name, code in CASES.items():
    r = run_code(code, timeout=3)
    print(f"--- {name} ---")
    print(format_result(r)[:400], "\n")

print("=" * 60, "\nEnd to end: generate, extract, run")
o = Orchestrator()
answer = o.handle("How to reverse a string")
print(answer[:600])
code = extract_code(answer)
if code:
    print(format_result(run_code(code)))
else:
    print("(no code block in the answer, probably a not-found reply)")
