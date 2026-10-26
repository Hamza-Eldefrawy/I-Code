from src import config
from src.llm import LLM
from src.retriever import Retriever
from src.memory import Memory
import re
from datetime import datetime, timezone
from uuid import uuid4


CODE_BLOCK = re.compile(r"```[\w+-]*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str | None:
    """Return the contents of all fenced code blocks, or None if there are none."""
    blocks = [b.strip("\n") for b in CODE_BLOCK.findall(text)]
    return "\n\n".join(blocks) if blocks else None

class Orchestrator:
  def __init__(self, llm: LLM, retriever: Retriever):
    self.llm = llm
    self.retriever = retriever
    self.memory = Memory(self.llm)
    self.awaiting_solution = False
    self.pending_request = None
  
  def handle(self, query: str) -> str:
    answer = self._route(query)          
    self.memory.add("user", query)
    self.memory.add("assistant", answer)
    return answer
  
  def _route(self, query: str) -> str:
    if self.awaiting_solution:
      # User is providing a solution to a previous request
      code = extract_code(query)
      self.awaiting_solution = False
      self.pending_request = None
      if code:
        doc_id = self.ingest_solution(self.pending_request, code)
        return "Thanks, I've learned this. Ask your question again and I'll use it."
    
    # router
    intent = self.llm.classify(query, context=self.memory.last_exchange())
    # Explain intent
    if intent == "explain":
      return self.explain(query)

    # Generate intent
    if intent == "generate":
      docs = self.retriever.search(query, k=config.TOP_K)
      if self.llm.evaluate(query, docs) == "relevant":
        return self.generate(query, docs)
    
    # Not found
    self.awaiting_solution = True
    self.pending_request = query
    return config.NOT_FOUND_MESSAGE

  def explain(self,query: str) -> str:
    mem = self.memory.as_prompt()
    prompt = f"{mem}\n\nCurrent request:\n{query}" if mem else query
    return self.llm.chat(prompt, system=config.EXPLAIN_PROMPT)

  def generate(self, query: str, docs: list[dict]) -> str:
    mem = self.memory.as_prompt()
    context = "\n\n".join(f"### Example {i + 1}\n{d['document']}" for i, d in enumerate(docs))
    prompt = (f"{mem}\n\n" if mem else "") + f"Reference examples:\n{context}\n\nCurrent request:\n{query}"
    return self.llm.chat(prompt, system=config.GENERATE_PROMPT)

  def ingest_solution(self, request: str, solution: str) -> str:
    """Store the user's solution, labeled with the request it answers."""
    doc_id = f"user_{uuid4().hex[:10]}"
    self.retriever.add(
        documents=[f"# Task: {request}\n\n{solution}"],
        metadatas=[{
            "source": "user_feedback",
            "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }],
        ids=[doc_id],
    )
    return doc_id
