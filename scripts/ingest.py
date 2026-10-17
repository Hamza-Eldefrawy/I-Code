import json
from src import config
from src.retriever import Retriever


def main():
    retriever = Retriever()

    if retriever.has_source("humaneval"):
        print(f"HumanEval already ingested ({retriever.count()} records). Nothing to do.")
        return

    if not config.DATASET_PATH.exists():
        raise SystemExit(f"{config.DATASET_PATH} not found. Run scripts.download_humaneval first.")

    rows = [json.loads(line)
            for line in config.DATASET_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()]

    retriever.add(
        documents=[r["prompt"] + r["canonical_solution"] for r in rows],
        metadatas=[{"source": "humaneval", "task_id": r["task_id"],
                    "entry_point": r["entry_point"]} for r in rows],
        ids=[r["task_id"] for r in rows],
    )
    print(f"Ingested {len(rows)} problems. Collection size: {retriever.count()}")


if __name__ == "__main__":
    main()
