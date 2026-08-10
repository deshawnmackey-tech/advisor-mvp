import os
import uuid
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import Json


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _fetch_latest_analysis(conn, client_id: str) -> dict:
    """Fetch latest analysis payload from common candidate tables."""
    candidate_queries = [
        (
            "analysis_runs",
            "SELECT result FROM analysis_runs WHERE client_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
        ),
        (
            "analysis_results",
            "SELECT payload FROM analysis_results WHERE client_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
        ),
        (
            "advisory_results",
            "SELECT result FROM advisory_results WHERE client_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
        ),
    ]

    with conn.cursor() as cur:
        for table_name, sql in candidate_queries:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                (table_name,),
            )
            exists = cur.fetchone()[0]
            if not exists:
                continue

            cur.execute(sql, (client_id,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]

    raise RuntimeError(
        "No analysis payload found. Expected one of: analysis_runs, analysis_results, advisory_results"
    )


def _build_cards(client_id: str, analysis: dict) -> list[dict]:
    snapshot = analysis.get("snapshot", {})
    actions = analysis.get("actions", [])
    disclaimer = analysis.get("disclaimer", "This is educational guidance, not financial advice.")

    cards: list[dict] = []

    if snapshot:
        cards.append(
            {
                "id": str(uuid.uuid4()),
                "client_id": client_id,
                "title": "Current Snapshot",
                "markdown": "## Current Snapshot\n\n```json\n" + str(snapshot) + "\n```",
                "payload": {
                    "type": "snapshot",
                    "snapshot": snapshot,
                    "disclaimer": disclaimer,
                },
            }
        )

    for idx, action in enumerate(actions, start=1):
        cards.append(
            {
                "id": str(uuid.uuid4()),
                "client_id": client_id,
                "title": f"Action {idx}",
                "markdown": f"## Action {idx}\n\n- {action}",
                "payload": {
                    "type": "action",
                    "priority": idx,
                    "action": action,
                    "disclaimer": disclaimer,
                },
            }
        )

    if not cards:
        cards.append(
            {
                "id": str(uuid.uuid4()),
                "client_id": client_id,
                "title": "No Structured Insights",
                "markdown": "No structured snapshot/actions found in latest analysis payload.",
                "payload": {
                    "type": "empty",
                    "disclaimer": disclaimer,
                },
            }
        )

    return cards


def _ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS insight_cards (
                id UUID PRIMARY KEY,
                client_id TEXT NOT NULL,
                title TEXT NOT NULL,
                markdown TEXT NOT NULL,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()


def _insert_cards(conn, cards: list[dict]):
    with conn.cursor() as cur:
        for card in cards:
            cur.execute(
                """
                INSERT INTO insight_cards (id, client_id, title, markdown, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    card["id"],
                    card["client_id"],
                    card["title"],
                    card["markdown"],
                    Json(card["payload"]),
                    datetime.now(timezone.utc),
                ),
            )
    conn.commit()


def main():
    client_id = os.getenv("CLIENT_ID", "demo_client")
    dsn = _require_env("DATABASE_URL")

    with psycopg2.connect(dsn=dsn) as conn:
        _ensure_table(conn)
        latest_analysis = _fetch_latest_analysis(conn, client_id)
        cards = _build_cards(client_id, latest_analysis)
        _insert_cards(conn, cards)

    print(f"Inserted {len(cards)} insight cards for client_id={client_id}")


if __name__ == "__main__":
    main()
