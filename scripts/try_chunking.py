import json
from src import config
from src.retriever import Retriever

r = Retriever()
print("Records:", r.count())

rows = {}
for line in config.DATASET_PATH.read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        rows[row["task_id"]] = row["prompt"] + row["canonical_solution"]

got = r.collection.get(where={"n_chunks": {"$gt": 1}})
split_ids = sorted({m["parent_id"] for m in got["metadatas"]})
print(f"Split documents: {len(split_ids)} -> {split_ids}")

for pid in split_ids:
    full = r.get_full(pid)
    print(f"  {pid}: {len(rows[pid])} chars, rebuilt identical: {full == rows[pid]}")

# search returns whole documents, one hit per problem
for q in ["check if any two numbers in a list are closer than a threshold",
          "Build a Flask API with one endpoint"]:
    print(f"\nQ: {q}")
    for h in r.search(q):
        print(f"  {h['distance']:.3f}  {h['id']}  ({len(h['document'])} chars)")
