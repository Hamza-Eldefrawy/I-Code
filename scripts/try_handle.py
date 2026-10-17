from src.orchestrator import handle

print(handle("Explain this code:\n```python\ndef f(n):\n    return 1 if n < 2 else n * f(n-1)\n```"))
print("-----")
print(handle("Write a function to reverse a string"))
