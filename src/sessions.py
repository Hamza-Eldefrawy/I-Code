import uuid
from src.orchestrator import Orchestrator


class SessionStore:
    def __init__(self, llm, retriever):
        self.llm, self.retriever = llm, retriever
        self._sessions: dict[str, Orchestrator] = {}

    def create(self) -> str:
        sid = uuid.uuid4().hex
        self._sessions[sid] = Orchestrator(self.llm, self.retriever)
        return sid

    def get(self, sid: str) -> Orchestrator | None:
        return self._sessions.get(sid)

    def delete(self, sid: str) -> None:
        self._sessions.pop(sid, None)