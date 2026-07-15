"""
DocumentRetriever — semantic search over insight cards.

Storage backends (tried in order):
  1. Local JSON store  — /tmp/docs_{client_id}.json  (no DB needed, default for dev)
  2. PostgreSQL        — insight_cards table (production, requires DATABASE_URL)

FAISS index files (always required):
  /tmp/faiss_{client_id}.index
  /tmp/idmap_{client_id}.json

Build the index for a client by running:
    python ingest/build_index.py --client demo_client
"""

import json
import os
from pathlib import Path
from typing import Dict, List


class DocumentRetriever:
    """Retrieve top-k insight cards by semantic similarity for a client."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self._embedder = None   # lazy-load — heavy model, only load when needed
        self.index, self.id_map = self._load_faiss()

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedder

    def _load_faiss(self):
        import faiss
        idx_path = f"/tmp/faiss_{self.client_id}.index"
        map_path = f"/tmp/idmap_{self.client_id}.json"

        if not os.path.exists(idx_path):
            raise FileNotFoundError(f"FAISS index not found: {idx_path}")
        if not os.path.exists(map_path):
            raise FileNotFoundError(f"FAISS id map not found: {map_path}")

        index = faiss.read_index(idx_path)
        with open(map_path, "r", encoding="utf-8") as f:
            id_map = json.load(f)   # {"0": "doc-uuid", "1": "doc-uuid", ...}

        return index, id_map

    def _fetch_from_local(self, doc_ids: List[str]) -> List[Dict]:
        """Read documents from the local JSON store built by build_index.py."""
        store_path = Path(f"/tmp/docs_{self.client_id}.json")
        if not store_path.exists():
            return []
        docs = json.loads(store_path.read_text())
        return [d for d in docs if d.get("id") in doc_ids]

    def _fetch_from_postgres(self, doc_ids: List[str]) -> List[Dict]:
        """Read documents from the PostgreSQL insight_cards table."""
        import psycopg2
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            return []
        try:
            with psycopg2.connect(dsn=dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT markdown, payload FROM insight_cards WHERE id = ANY(%s)",
                        (doc_ids,),
                    )
                    rows = cur.fetchall()
            return [{"markdown": r[0], "payload": json.loads(r[1])} for r in rows]
        except Exception:
            return []

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        embedder = self._get_embedder()
        q_vec = embedder.encode([query]).astype("float32")
        _, indices = self.index.search(q_vec, k)

        doc_ids = [
            self.id_map[str(i)]
            for i in indices[0]
            if i != -1 and str(i) in self.id_map
        ]
        if not doc_ids:
            return []

        # Try local store first, fall back to Postgres
        docs = self._fetch_from_local(doc_ids)
        if not docs:
            docs = self._fetch_from_postgres(doc_ids)

        return docs
