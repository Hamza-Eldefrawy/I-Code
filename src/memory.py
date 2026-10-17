from src import config


class Memory:
    def __init__(self, llm, max_messages: int = config.MEMORY_MAX_MESSAGES,
                batch: int = config.MEMORY_SUMMARY_BATCH):
        self.llm = llm
        self.max_messages = max_messages
        self.batch = batch
        self.messages: list[dict] = []    # {"role": "user"/"assistant", "content": ...}
        self.summary: str = ""            # covers everything that left the window
        self.preferences: dict = {}       # filled from the UI dropdowns

    def set_preferences(self, language: str | None = None, framework: str | None = None) -> None:
        prefs = {"language": language, "framework": framework}
        self.preferences = {k: v for k, v in prefs.items() if v}

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages + self.batch:
            self._compress()

    def _compress(self) -> None:
        old = self.messages[:-self.max_messages]
        try:
            new_summary = self.llm.summarize(self.summary, old)
        except Exception:
            return                        # LLM failed: keep everything, retry on the next message
        if new_summary:
            self.summary = new_summary
            self.messages = self.messages[-self.max_messages:]

    def as_prompt(self) -> str:
        parts = []
        if self.preferences:
            parts.append("User preferences: " + ", ".join(f"{k}={v}" for k, v in self.preferences.items()))
        if self.summary:
            parts.append("Summary of the earlier conversation:\n" + self.summary)
        if self.messages:
            lines = [f"{m['role'].capitalize()}: {m['content']}" for m in self.messages]
            parts.append("Recent messages:\n" + "\n\n".join(lines))
        return "\n\n".join(parts)

    def last_exchange(self, limit: int = 600) -> str:
        """Last user+assistant pair, shortened. Only used so the classifier can read follow-ups."""
        return "\n".join(
            f"{m['role'].capitalize()}: {m['content'][:limit]}" for m in self.messages[-2:]
        )

    def clear(self) -> None:
        self.messages, self.summary, self.preferences = [], "", {}