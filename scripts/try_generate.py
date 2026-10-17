from src.orchestrator import Orchestrator

o = Orchestrator()

QUERIES = [
    "Write a function that checks if any two numbers in a list are closer than a threshold",  # in scope
    "Write a function to return the sum of the digits of a number",                          # likely in scope
    "Build a Flask API with one endpoint",                                                   # out of scope
    "Generate a CNN model in PyTorch",                                                       # out of scope
]

for q in QUERIES:
    print("=" * 70)
    print("Q:", q)
    docs = o.retriever.search(q)
    for d in docs:
        print(f"   {d['distance']:.3f}  {d['id']}")
    print("   evaluator:", o.llm.evaluate(q, docs))
    print("-" * 70)
    print(o.handle(q))
