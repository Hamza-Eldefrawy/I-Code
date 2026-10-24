import re
import sqlite3
from pathlib import Path

import pandas as pd

from src import config


def clean_name(name, fallback: str) -> str:
    """'Salary ($)' -> 'salary', 'Order Date' -> 'order_date'."""
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name)).strip("_").lower()
    if not s:
        return fallback
    return f"_{s}" if s[0].isdigit() else s


class SQLiteDB:
    def __init__(self):
        # check_same_thread=False: Streamlit may run reruns on different threads
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.table: str | None = None

    def is_loaded(self) -> bool:
        return self.table is not None

    # ---------- load ----------

    def load_csv(self, path: str, table: str | None = None) -> dict:
        """Read a CSV, clean its column names and store it as one SQLite table.
        A new load replaces the previous table. Returns a short summary."""
        try:
            df = pd.read_csv(path)
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="latin-1")

        seen, cols = {}, []
        for i, c in enumerate(df.columns):
            base = clean_name(c, f"col_{i + 1}")
            seen[base] = seen.get(base, 0) + 1
            cols.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
        df.columns = cols

        name = clean_name(table or Path(path).stem, "data")

        self.conn.execute("PRAGMA query_only = OFF")           # allow writing while loading
        if self.table and self.table != name:
            self.conn.execute(f'DROP TABLE IF EXISTS "{self.table}"')
        df.to_sql(name, self.conn, if_exists="replace", index=False)
        self.conn.commit()
        self.conn.execute("PRAGMA query_only = ON")            # read-only from now
        self.table = name
        return {"table": name, "rows": len(df), "columns": cols}

    # ---------- schema for the prompt ----------

    def schema(self) -> str:
        if not self.is_loaded():
            return ""
        info = self.conn.execute(f'PRAGMA table_info("{self.table}")').fetchall()  # cid, name, type, ...
        names = [c[1] for c in info]
        ddl = f'CREATE TABLE "{self.table}" (\n' + ",\n".join(
            f'  "{c[1]}" {c[2] or "TEXT"}' for c in info) + "\n);"
        rows = self.conn.execute(
            f'SELECT * FROM "{self.table}" LIMIT {config.SQL_SAMPLE_ROWS}').fetchall()
        sample = "\n".join(" | ".join(str(v)[:60] for v in r) for r in rows)
        return f"{ddl}\n\nSample rows ({' | '.join(names)}):\n{sample}"

    # ---------- execute ----------

    def execute(self, sql: str, max_rows: int = config.SQL_MAX_ROWS) -> dict:
        """Run ONE read-only query. Raises on anything else or on SQL errors."""
        q = sql.strip().rstrip(";").strip()
        if not re.match(r"(?is)^(select|with)\b", q):
            raise ValueError("Only SELECT queries are allowed.")
        cur = self.conn.execute(q)       # query_only blocks writes; sqlite3 rejects multi-statement strings
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows + 1)
        return {"columns": columns, "rows": rows[:max_rows], "truncated": len(rows) > max_rows}


def format_table(result: dict, limit: int = 20) -> str:
    """Markdown table for showing a result in the chat."""
    cols, rows = result["columns"], result["rows"]
    if not rows:
        return "_No rows returned._"

    def cell(v):
        return "NULL" if v is None else str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    lines += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows[:limit]]
    if len(rows) > limit or result["truncated"]:
        more = "+" if result["truncated"] else ""
        lines.append(f"\nShowing {min(limit, len(rows))} of {len(rows)}{more} rows.")
    return "\n".join(lines)
