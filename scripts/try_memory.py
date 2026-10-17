from src.llm import LLM
from src.memory import Memory

m = Memory(LLM(), max_messages=4, batch=2)       # small numbers so it triggers quickly
m.set_preferences(language="Java", framework=None)

for i in range(4):
    m.add("user", f"Question {i}: write a Java class for part {i} of a student grade tracker")
    m.add("assistant", f"```java\nclass Part{i} {{ }}\n```\nHere is part {i}.")

print("Messages kept:", len(m.messages))          # 4 to 6, not 8
print("Summary:", m.summary or "(none)")
print(m.as_prompt())