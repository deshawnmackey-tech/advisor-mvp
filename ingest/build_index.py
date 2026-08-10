"""
Build a FAISS vector index and local document store for a client.

Reads the business profile JSON, generates advisory insight documents,
embeds them with sentence-transformers, and writes:
  /tmp/faiss_{client_id}.index   — FAISS L2 index
  /tmp/idmap_{client_id}.json    — position → doc_id map
  /tmp/docs_{client_id}.json     — full document store (markdown + payload)

Usage:
    python ingest/build_index.py --client demo_client
    python ingest/build_index.py --client demo_client --input path/to/business.json
"""

import argparse
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "sample_business.json"


def _load_business(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _generate_documents(client_id: str, business: dict) -> list[dict]:
    """Turn a business profile into a set of searchable advisory documents."""
    name = business.get("name", client_id)
    revenue = business.get("annual_revenue", 0)
    ebitda = business.get("ebitda", 0)
    margin = round(ebitda / revenue * 100, 1) if revenue else 0
    dscr = round(ebitda / max(business.get("annual_debt_service", 1), 1), 2)
    doc_pct = business.get("documentation_completeness_pct", 0)
    recurring = business.get("recurring_revenue_pct", 0)
    growth = business.get("yoy_revenue_growth_pct", 0)

    customers = business.get("customer_revenue", {})
    top_customer, top_amount = max(
        ((k, v) for k, v in customers.items() if k != "all_other_customers"),
        key=lambda kv: kv[1],
        default=("Unknown", 0),
    )
    concentration = round(top_amount / revenue * 100, 1) if revenue else 0

    docs = [
        {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "title": "Financial Overview",
            "text": (
                f"{name} generated ${revenue:,} in annual revenue with ${ebitda:,} EBITDA "
                f"({margin}% margin). Year-over-year revenue growth is {growth}%. "
                f"Debt service coverage ratio is {dscr}x."
            ),
            "payload": {"type": "financial_overview", "revenue": revenue, "ebitda": ebitda, "dscr": dscr},
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "title": "Customer Concentration Risk",
            "text": (
                f"{top_customer} accounts for {concentration}% of {name}'s annual revenue. "
                f"High concentration above 20% is a material risk for buyers and lenders. "
                f"Multi-year contracts reduce this risk significantly."
            ),
            "payload": {"type": "concentration_risk", "top_customer": top_customer, "concentration_pct": concentration},
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "title": "Recurring Revenue Quality",
            "text": (
                f"{recurring}% of {name}'s revenue is recurring. "
                f"Buyers and investors prefer 70%+ recurring revenue as it signals "
                f"earnings quality and reduces post-close revenue risk."
            ),
            "payload": {"type": "recurring_revenue", "recurring_pct": recurring},
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "title": "Documentation Readiness",
            "text": (
                f"{name} has {doc_pct}% of standard diligence documents ready. "
                f"A score below 85% will slow down any sale, loan, or investor process. "
                f"Priority items: 3 years of tax returns, bank reconciliations, org chart, "
                f"customer contracts, and employee agreements."
            ),
            "payload": {"type": "documentation", "completeness_pct": doc_pct},
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "title": "SBA Loan Readiness",
            "text": (
                f"SBA 7(a) loans require a minimum DSCR of 1.25x. {name} currently shows "
                f"{dscr}x DSCR. {'This is below the SBA threshold.' if dscr < 1.25 else 'This meets the minimum threshold.'} "
                f"Documentation completeness of {doc_pct}% also affects underwriting speed."
            ),
            "payload": {"type": "sba_loan", "dscr": dscr, "doc_completeness": doc_pct},
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "title": "Sale Readiness — Valuation Drivers",
            "text": (
                f"Key valuation drivers for {name}: recurring revenue ({recurring}%), "
                f"customer concentration ({concentration}% in top account), "
                f"owner dependency, and documentation completeness ({doc_pct}%). "
                f"Improving these metrics can add 0.5–1.5x to the sale multiple."
            ),
            "payload": {"type": "sale_readiness", "recurring_pct": recurring, "concentration_pct": concentration},
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "title": "Investor Readiness",
            "text": (
                f"{name} shows {growth}% YoY revenue growth. Investors at seed stage typically "
                f"look for 30%+ growth. EBITDA margin of {margin}% and net revenue retention "
                f"are key unit economics to strengthen before fundraising."
            ),
            "payload": {"type": "investor_readiness", "growth_pct": growth, "margin_pct": margin},
        },
    ]

    return docs


def build_index(client_id: str, business: dict) -> None:
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    print(f"Building index for client: {client_id}")
    docs = _generate_documents(client_id, business)
    print(f"  Generated {len(docs)} documents")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [f"{d['title']}. {d['text']}" for d in docs]
    embeddings = model.encode(texts, show_progress_bar=True).astype("float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    idx_path = f"/tmp/faiss_{client_id}.index"
    map_path = f"/tmp/idmap_{client_id}.json"
    docs_path = f"/tmp/docs_{client_id}.json"

    faiss.write_index(index, idx_path)
    print(f"  FAISS index written → {idx_path}")

    id_map = {str(i): docs[i]["id"] for i in range(len(docs))}
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(id_map, f)
    print(f"  ID map written      → {map_path}")

    doc_store = [
        {"id": d["id"], "client_id": d["client_id"], "markdown": f"## {d['title']}\n\n{d['text']}", "payload": d["payload"]}
        for d in docs
    ]
    with open(docs_path, "w", encoding="utf-8") as f:
        json.dump(doc_store, f, indent=2)
    print(f"  Doc store written   → {docs_path}")
    print(f"Done. {len(docs)} documents indexed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAISS index for a client.")
    parser.add_argument("--client", default="demo_client", help="Client ID")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to business JSON")
    args = parser.parse_args()

    business = _load_business(Path(args.input))
    build_index(args.client, business)


if __name__ == "__main__":
    main()
