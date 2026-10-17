import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from src import config


class Retriever:
    def __init__(self):
        client = chromadb.PersistentClient(path=config.CHROMA_PATH)
        self.collection = client.get_or_create_collection(
            name=config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        # No overlap + keep whitespace/separators => "".join(chunks) == original text
        self.splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.PYTHON,
            chunk_size=config.CHUNK_THRESHOLD,
            chunk_overlap=0,
            strip_whitespace=False # keep whitespace so that joining chunks is identical to original text
        )

    # ---------- write ----------

    def add(self, documents: list[str], metadatas: list[dict], ids: list[str]) -> None:
        """Split long documents, embed (Chroma does it) and upsert."""
        out_docs, out_meta, out_ids = [], [], []
        for text, meta, id_ in zip(documents, metadatas, ids):
            self.collection.delete(where={"parent_id": id_})   # drop stale chunks on re-add
            parts = [text] if len(text) <= config.CHUNK_THRESHOLD else self.splitter.split_text(text)
            for i, part in enumerate(parts):
                out_docs.append(part)
                out_meta.append({**meta, "parent_id": id_, "chunk": i, "n_chunks": len(parts)})
                out_ids.append(id_ if len(parts) == 1 else f"{id_}#{i}")
        self.collection.upsert(documents=out_docs, metadatas=out_meta, ids=out_ids)

    # ---------- read ----------

    def get_full(self, parent_id: str) -> str:
        """Rebuild a document from all its chunks, in order."""
        got = self.collection.get(where={"parent_id": parent_id})
        pairs = sorted(zip(got["metadatas"], got["documents"]), key=lambda p: p[0]["chunk"])
        return "".join(doc for _, doc in pairs)

    def search(self, query: str, k: int = config.TOP_K) -> list[dict]:
        """Top-k DOCUMENTS (not chunks). Each hit carries the full text."""
        res = self.collection.query(query_texts=[query], n_results=k * 3)
        hits, seen = [], set()
        for id_, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            parent = meta["parent_id"]
            if parent in seen:
                continue
            seen.add(parent)
            if meta["n_chunks"] > 1:
                doc = self.get_full(parent)  # swap the chunk for the whole document
            hits.append({"id": parent, "document": doc, "metadata": meta, "distance": dist})
            if len(hits) == k:
                break
        return hits

    def has_source(self, source: str) -> bool:
        got = self.collection.get(where={"source": source}, limit=1)
        return len(got["ids"]) > 0

    def count(self) -> int:
        return self.collection.count()
