from src.llm import LLM

llm = LLM()
print(llm.chat("Reply with exactly one word: hello"))
print(llm.classify("Write a function to reverse a string"))
