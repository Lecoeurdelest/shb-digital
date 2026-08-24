"""Idempotent batch backfill from PostgreSQL notes into the derived Qdrant index."""

from __future__ import annotations

import argparse
from typing import Any

import numpy as np

from app.retrieval.vector_notes import _NAMESPACE
from app.storage import vector_capability
from app.storage.registry import connect_core


def _records(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    records = []
    for note_id, owner_id, ts, channel, note_text, embedding in rows:
        vector = np.frombuffer(bytes(embedding), dtype=np.float32).tolist()
        if not vector:
            raise ValueError(f"note {note_id} has an empty embedding")
        records.append(
            {
                "id": int(note_id),
                "vector": vector,
                "metadata": {
                    "note_id": int(note_id),
                    "owner_id": str(owner_id),
                    "ts": str(ts),
                    "channel": str(channel),
                    "text": str(note_text),
                },
            }
        )
    return records


def sync_notes(*, batch_size: int = 500, after_note_id: int = 0) -> int:
    if batch_size < 1 or batch_size > 5_000:
        raise ValueError("batch_size must be between 1 and 5000")
    if after_note_id < 0:
        raise ValueError("after_note_id must not be negative")
    store = vector_capability()
    last_note_id = after_note_id
    total = 0
    conn = connect_core()
    try:
        while True:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT note_id, owner_id, ts, channel, note_text, embedding
                    FROM interaction_notes
                    WHERE note_id > %s AND embedding IS NOT NULL
                    ORDER BY note_id
                    LIMIT %s
                    """,
                    (last_note_id, batch_size),
                )
                rows = cur.fetchall()
            if not rows:
                break
            store.upsert(_NAMESPACE, _records(rows))
            total += len(rows)
            last_note_id = int(rows[-1][0])
    finally:
        conn.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill PostgreSQL interaction notes into Qdrant")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--after-note-id", type=int, default=0)
    args = parser.parse_args()
    print(f"synced_notes={sync_notes(batch_size=args.batch_size, after_note_id=args.after_note_id)}")


if __name__ == "__main__":
    main()
