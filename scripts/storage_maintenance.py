#!/usr/bin/env python3
"""Offline storage maintenance for ChatGuardian SQLite databases.

Examples:
  python scripts/storage_maintenance.py --db data/db.sqlite --strip-images --prune
  python scripts/storage_maintenance.py --db data/db.sqlite --compact

VACUUM/--compact may require temporary free disk space roughly comparable to the
database size. Prefer running --strip-images --prune first, then compact only
when the device has enough free space.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def _image_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:5].upper()


def _estimate_base64_size(value: str) -> int:
    stripped = "".join(value.split())
    if not stripped:
        return 0
    padding = 2 if stripped.endswith("==") else 1 if stripped.endswith("=") else 0
    return max(0, (len(stripped) * 3 // 4) - padding)


def _strip_message_payload(payload: dict[str, Any]) -> bool:
    changed = False
    for item in payload.get("contents") or []:
        if not isinstance(item, dict) or item.get("type") != "image":
            continue
        raw = item.pop("image_data", None)
        if raw is None:
            continue
        raw_str = raw if isinstance(raw, str) else str(raw)
        item.setdefault("image_id", _image_id(raw_str))
        item.setdefault("image_byte_size", _estimate_base64_size(raw_str))
        item["image_data_stripped"] = True
        changed = True
    reply = payload.get("reply_from")
    if isinstance(reply, dict):
        changed = _strip_message_payload(reply) or changed
    return changed


def _strip_detection_payload(payload: dict[str, Any]) -> bool:
    changed = False
    for message in payload.get("context_messages") or []:
        if isinstance(message, dict):
            changed = _strip_message_payload(message) or changed
    return changed


def _process_json_rows(
        conn: sqlite3.Connection,
        *,
        table: str,
        json_column: str,
        stripper,
        batch_size: int,
) -> int:
    changed_rows = 0
    last_id = 0
    while True:
        rows = conn.execute(
            f"SELECT id, {json_column} FROM {table} "
            f"WHERE id > ? AND {json_column} LIKE '%\"image_data\"%' "
            f"ORDER BY id LIMIT ?",
            (last_id, batch_size),
        ).fetchall()
        if not rows:
            break
        for row_id, raw_json in rows:
            last_id = row_id
            try:
                payload = json.loads(raw_json)
            except Exception:
                continue
            if not isinstance(payload, dict) or not stripper(payload):
                continue
            conn.execute(
                f"UPDATE {table} SET {json_column} = ? WHERE id = ?",
                (json.dumps(payload, ensure_ascii=False, separators=(",", ":")), row_id),
            )
            changed_rows += 1
        conn.commit()
    return changed_rows


def strip_images(conn: sqlite3.Connection, batch_size: int) -> dict[str, int]:
    return {
        "chat_messages_stripped": _process_json_rows(
            conn,
            table="chat_messages",
            json_column="message_json",
            stripper=_strip_message_payload,
            batch_size=batch_size,
        ),
        "detection_results_stripped": _process_json_rows(
            conn,
            table="detection_results",
            json_column="payload_json",
            stripper=_strip_detection_payload,
            batch_size=batch_size,
        ),
    }


def prune(conn: sqlite3.Connection, args: argparse.Namespace) -> dict[str, int]:
    result = {
        "history_deleted_by_age": 0,
        "history_deleted_by_count": 0,
        "detection_deleted_by_age": 0,
        "detection_deleted_by_count": 0,
    }
    now = dt.datetime.now(dt.timezone.utc)

    if args.history_retention_days > 0:
        cutoff = (now - dt.timedelta(days=args.history_retention_days)).replace(tzinfo=None).isoformat(" ")
        cur = conn.execute(
            "DELETE FROM chat_messages "
            "WHERE bucket = 'history' AND message_timestamp IS NOT NULL AND message_timestamp < ?",
            (cutoff,),
        )
        result["history_deleted_by_age"] = cur.rowcount if cur.rowcount != -1 else 0

    if args.max_history_messages > 0:
        ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM chat_messages WHERE bucket = 'history' ORDER BY id DESC "
                "LIMIT -1 OFFSET ?",
                (args.max_history_messages,),
            )
        ]
        if ids:
            conn.executemany("DELETE FROM chat_messages WHERE id = ?", [(row_id,) for row_id in ids])
            result["history_deleted_by_count"] = len(ids)

    if args.retention_days > 0:
        cutoff = (now - dt.timedelta(days=args.retention_days)).replace(tzinfo=None).isoformat(" ")
        cur = conn.execute("DELETE FROM detection_results WHERE generated_at < ?", (cutoff,))
        result["detection_deleted_by_age"] = cur.rowcount if cur.rowcount != -1 else 0

    if args.max_results_per_rule > 0:
        rule_ids = [row[0] for row in conn.execute("SELECT DISTINCT rule_id FROM detection_results")]
        delete_ids: list[int] = []
        for rule_id in rule_ids:
            delete_ids.extend(
                row[0]
                for row in conn.execute(
                    "SELECT id FROM detection_results WHERE rule_id = ? ORDER BY id DESC "
                    "LIMIT -1 OFFSET ?",
                    (rule_id, args.max_results_per_rule),
                )
            )
        if delete_ids:
            conn.executemany("DELETE FROM detection_results WHERE id = ?", [(row_id,) for row_id in delete_ids])
            result["detection_deleted_by_count"] = len(delete_ids)

    conn.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain a ChatGuardian SQLite database.")
    parser.add_argument("--db", required=True, help="Path to db.sqlite")
    parser.add_argument("--strip-images", action="store_true", help="Remove base64 image_data from JSON payloads")
    parser.add_argument("--prune", action="store_true", help="Delete expired/over-limit rows")
    parser.add_argument("--compact", action="store_true", help="Run SQLite VACUUM")
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--max-results-per-rule", type=int, default=1000)
    parser.add_argument("--history-retention-days", type=int, default=30)
    parser.add_argument("--max-history-messages", type=int, default=100000)
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"Database file not found: {db_path}")

    before = db_path.stat().st_size
    summary: dict[str, Any] = {"before_bytes": before}
    with sqlite3.connect(db_path) as conn:
        if args.strip_images:
            summary.update(strip_images(conn, max(1, args.batch_size)))
        if args.prune:
            summary.update(prune(conn, args))
        if args.compact:
            conn.execute("VACUUM")
            conn.commit()
            summary["compacted"] = True

    summary["after_bytes"] = db_path.stat().st_size
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
