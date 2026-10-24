import tempfile
from pathlib import Path

import pandas as pd

from src.llm import LLM
from src.sql import SQLiteDB, format_table

# ---------- build a sample CSV with awkward headers ----------
df = pd.DataFrame({
    "Employee Name": ["Ana", "Ben", "Chen", "Dina", "Eli", "Farah", "Gus", "Hana", "Ivan", "Jade", "Kai", "Lena"],
    "Department":    ["Engineering", "Engineering", "Sales", "Sales", "HR", "Engineering",
                      "Sales", "HR", "Engineering", "Sales", "Engineering", "HR"],
    "Salary ($)":    [5200, 6100, 3900, 4300, 3500, 7000, 4100, 3700, 5800, 4600, 6400, 3600],
    "Hire Date":     ["2019-03-15", "2020-07-01", "2021-02-10", "2022-05-20", "2018-11-30", "2021-09-01",
                      "2023-01-15", "2020-01-20", "2022-08-08", "2019-12-12", "2023-04-04", "2021-06-30"],
    "City":          ["Cairo", "Cairo", "Giza", "Cairo", "Giza", "Cairo",
                      "Alexandria", "Giza", "Cairo", "Alexandria", "Giza", "Cairo"],
})
csv_path = Path(tempfile.mkdtemp()) / "employees.csv"
df.to_csv(csv_path, index=False)

db, llm = SQLiteDB(), LLM()
print(db.load_csv(str(csv_path)))
print("\n" + db.schema())


def ask(question: str):
    schema = db.schema()
    sql = llm.text2sql(question, schema)
    for attempt in range(2):                    # first try + one retry
        try:
            return sql, db.execute(sql)
        except Exception as e:
            if attempt == 1:
                return sql, f"ERROR: {e}"
            sql = llm.text2sql(question, schema, previous_sql=sql, error=str(e))


expected = {
    "How many employees are there?": len(df),
    "What is the average salary in Engineering?": df[df.Department == "Engineering"]["Salary ($)"].mean(),
    "Who are the 3 highest paid employees?": df.nlargest(3, "Salary ($)")["Employee Name"].tolist(),
    "How many employees are in each department?": df.Department.value_counts().to_dict(),
    "How many employees were hired after 2021-01-01?": int((df["Hire Date"] > "2021-01-01").sum()),
    "Which city has the most employees?": df.City.value_counts().idxmax(),
}

for q, exp in expected.items():
    print("\n" + "=" * 70)
    print("Q:", q)
    sql, result = ask(q)
    print("SQL:", sql)
    print(result if isinstance(result, str) else format_table(result))
    print("EXPECTED (pandas):", exp)

# ---------- safety: each of these must be rejected ----------
print("\n" + "=" * 70, "\nSafety checks")
for bad in ["DELETE FROM employees",
            "WITH x AS (SELECT 1) DELETE FROM employees",
            "SELECT * FROM employees; DROP TABLE employees",
            "PRAGMA query_only = OFF"]:
    try:
        db.execute(bad)
        print("NOT BLOCKED:", bad)
    except Exception as e:
        print("blocked:", bad[:45], "->", type(e).__name__)
print("rows still there:", db.execute('SELECT COUNT(*) FROM "employees"')["rows"])
