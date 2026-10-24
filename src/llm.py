import re
from openai import OpenAI
from src import config


class LLM:
    def __init__(self, model: str = config.MODEL):
        self.model = model
        self.client = OpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            timeout=30.0, # try deepseek
        )

    def chat(self, prompt: str, system: str | None = None,
            temperature: float | None = None, max_tokens: int | None = None) -> str:
        """Stateless single call. Returns the model's text."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=config.TEMPERATURE if temperature is None else temperature,
            max_tokens=max_tokens or config.MAX_TOKENS,
        )
        return (resp.choices[0].message.content or "").strip()

    def classify(self, query: str, context: str = "") -> str:
        """Returns 'explain' or 'generate'. Defaults to 'generate' if unclear."""
        prompt = f"Recent conversation:\n{context}\n\nNew message:\n{query}" if context else query
        raw = self.chat(prompt, system=config.CLASSIFIER_PROMPT, temperature=0, max_tokens=50)
        match = re.search(r"\b(explain|generate)\b", raw.lower())
        return match.group(1) if match else "could you clarify more?"

    def evaluate(self, query: str, docs: list[dict]) -> str:
        """Returns 'relevant' or 'not_relevant'. Defaults to 'not_relevant' if unclear."""
        # print("MODEL: ", self.model)
        context = "\n\n".join(
            f"[Document {i + 1}: {d['id']}]\n{d['document']}" for i, d in enumerate(docs)
        )
        prompt = f"User request:\n{query}\n\nRetrieved context:\n{context}"
        raw = self.chat(prompt, system=config.EVALUATOR_PROMPT,
                        temperature=0, max_tokens=200).lower()
        if re.search(r"\bnot[_ ]relevant\b", raw):   # check this first: it contains "relevant"
            return "not_relevant"
        if re.search(r"\brelevant\b", raw):
            return "relevant"
        return "not_clear"

    def summarize(self, summary: str, messages: list[dict]) -> str:
        text = "\n\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)
        prompt = f"Current summary:\n{summary or '(empty)'}\n\nOlder messages:\n{text}"
        return self.chat(prompt, system=config.SUMMARY_PROMPT, temperature=0.2, max_tokens=400)

    def text2sql(self, question: str, schema: str,
            previous_sql: str | None = None, error: str | None = None) -> str:
        """Returns a SQL string. Pass previous_sql and error to ask for a corrected query."""
        prompt = f"Schema:\n{schema}\n\nQuestion:\n{question}"
        if previous_sql and error:
            prompt += (f"\n\nYour previous query failed.\nQuery:\n{previous_sql}\n"
                        f"Error:\n{error}\nReturn a corrected query.")
        raw = self.chat(prompt, system=config.TEXT2SQL_PROMPT, temperature=0, max_tokens=800)
        m = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
        return (m.group(1) if m else raw).strip()

