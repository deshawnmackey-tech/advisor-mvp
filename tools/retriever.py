import json
import os
from typing import Dict, List

import faiss
import psycopg2
from sentence_transformers import SentenceTransformer


class DocumentRetriever:
    """Retrieve top-k insight cards by semantic similarity for a client."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.index, self.id_map = self._load_faiss()

    def _load_faiss(self):
        idx_path = f"/tmp/faiss_{self.client_id}.index"
        map_path = f"/tmp/idmap_{self.client_id}.json"

        if not os.path.exists(idx_path):
            raise FileNotFoundError(f"FAISS index not found: {idx_path}")
        if not os.path.exists(map_path):
            raise FileNotFoundError(f"FAISS id map not found: {map_path}")

        index = faiss.read_index(idx_path)
        with open(map_path, "r", encoding="utf-8") as f:
            id_map = json.load(f)  # {position: doc_id}

        return index, id_map

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        q_vec = self.embedder.encode([query]).astype("float32")
        _, indices = self.index.search(q_vec, k)

        doc_ids = [
            self.id_map[str(i)]
            for i in indices[0]
            if i != -1 and str(i) in self.id_map
        ]
        if not doc_ids:
            return []

        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise ValueError("DATABASE_URL is not set")

        with psycopg2.connect(dsn=dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT markdown, payload FROM insight_cards WHERE id = ANY(%s)",
                    (doc_ids,),
                )
                rows = cur.fetchall()

        return [{"markdown": r[0], "payload": json.loads(r[1])} for r in rows]
