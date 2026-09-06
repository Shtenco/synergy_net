from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4


@dataclass(frozen=True)
class TransportPacket:
    network_message_id: str
    event_id: str
    topic: str
    source_repo: str
    destination_repo: str
    payload: bytes
    payload_hash: str


@dataclass(frozen=True)
class ClaimedPacket:
    packet: TransportPacket
    attempts: int
    lease_until: str


class SynergyNetTransport:
    """Opaque transport authority.

    The payload is never interpreted as finance/accounting/policy by this layer.
    SynergyNet owns transport reliability only.
    """

    authority = "p2p_transport"
    execution_authority = "NONE"
    accounting_authority = "NONE"
    payment_authority = "NONE"
    validator_authority = "NONE"

    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._create_schema()

    def close(self) -> None:
        self.conn.close()

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS transport_spool (
                network_message_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE,
                topic TEXT NOT NULL,
                source_repo TEXT NOT NULL,
                destination_repo TEXT NOT NULL,
                payload BLOB NOT NULL,
                payload_hash TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('PENDING','INFLIGHT','RETRY','ACKED','DEAD')),
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT NOT NULL,
                lease_until TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_error TEXT
            );

            CREATE TABLE IF NOT EXISTS transport_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                network_message_id TEXT NOT NULL,
                attempt_no INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                error TEXT,
                attempted_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transport_dead_letter (
                network_message_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                reason TEXT NOT NULL,
                failed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_transport_ready
              ON transport_spool(state, next_attempt_at, created_at);
            CREATE INDEX IF NOT EXISTS idx_transport_lease
              ON transport_spool(state, lease_until);
            """
        )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    @staticmethod
    def _hash(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _parse(value: str) -> datetime:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _format(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def enqueue(
        self,
        *,
        event_id: str,
        topic: str,
        source_repo: str,
        destination_repo: str,
        payload: bytes,
        now: str,
        network_message_id: str | None = None,
    ) -> TransportPacket:
        payload_hash = self._hash(payload)
        with self.transaction() as tx:
            existing = tx.execute("SELECT * FROM transport_spool WHERE event_id=?", (event_id,)).fetchone()
            if existing is not None:
                if existing["payload_hash"] != payload_hash:
                    raise ValueError("same event_id reused with different wire payload")
                if existing["topic"] != topic or existing["destination_repo"] != destination_repo:
                    raise ValueError("same event_id reused with conflicting route")
                return TransportPacket(
                    network_message_id=existing["network_message_id"],
                    event_id=existing["event_id"],
                    topic=existing["topic"],
                    source_repo=existing["source_repo"],
                    destination_repo=existing["destination_repo"],
                    payload=bytes(existing["payload"]),
                    payload_hash=existing["payload_hash"],
                )
            message_id = network_message_id or str(uuid4())
            tx.execute(
                """
                INSERT INTO transport_spool(
                    network_message_id,event_id,topic,source_repo,destination_repo,payload,payload_hash,
                    state,attempts,next_attempt_at,lease_until,created_at,updated_at,last_error
                ) VALUES (?,?,?,?,?,?,?,'PENDING',0,?,NULL,?,?,NULL)
                """,
                (message_id,event_id,topic,source_repo,destination_repo,payload,payload_hash,now,now,now),
            )
        return TransportPacket(message_id,event_id,topic,source_repo,destination_repo,payload,payload_hash)

    def recover_stale(self, now: str) -> int:
        with self.transaction() as tx:
            cursor = tx.execute(
                """
                UPDATE transport_spool
                SET state='RETRY', lease_until=NULL, updated_at=?,
                    last_error=COALESCE(last_error,'transport lease expired before ack')
                WHERE state='INFLIGHT' AND lease_until IS NOT NULL AND lease_until <= ?
                """,
                (now, now),
            )
            return cursor.rowcount

    def claim(self, now: str, limit: int = 100, lease_seconds: int = 30) -> list[ClaimedPacket]:
        if limit <= 0:
            return []
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        lease_until = self._format(self._parse(now) + timedelta(seconds=lease_seconds))
        with self.transaction() as tx:
            tx.execute(
                """
                UPDATE transport_spool
                SET state='RETRY', lease_until=NULL, updated_at=?,
                    last_error=COALESCE(last_error,'transport lease expired before ack')
                WHERE state='INFLIGHT' AND lease_until IS NOT NULL AND lease_until <= ?
                """,
                (now, now),
            )
            rows = tx.execute(
                """
                SELECT * FROM transport_spool
                WHERE state IN ('PENDING','RETRY') AND next_attempt_at <= ?
                ORDER BY created_at, network_message_id
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
            result: list[ClaimedPacket] = []
            for row in rows:
                attempts = int(row["attempts"]) + 1
                cursor = tx.execute(
                    """
                    UPDATE transport_spool
                    SET state='INFLIGHT', attempts=?, lease_until=?, updated_at=?
                    WHERE network_message_id=? AND state IN ('PENDING','RETRY')
                    """,
                    (attempts, lease_until, now, row["network_message_id"]),
                )
                if cursor.rowcount != 1:
                    continue
                packet = TransportPacket(
                    row["network_message_id"], row["event_id"], row["topic"], row["source_repo"],
                    row["destination_repo"], bytes(row["payload"]), row["payload_hash"],
                )
                result.append(ClaimedPacket(packet, attempts, lease_until))
            return result

    def ack(self, network_message_id: str, now: str) -> None:
        with self.transaction() as tx:
            row = tx.execute("SELECT state,attempts FROM transport_spool WHERE network_message_id=?", (network_message_id,)).fetchone()
            if row is None:
                raise KeyError(network_message_id)
            if row["state"] != "INFLIGHT":
                raise ValueError("only INFLIGHT packet can be acked")
            tx.execute(
                "UPDATE transport_spool SET state='ACKED',lease_until=NULL,updated_at=?,last_error=NULL WHERE network_message_id=?",
                (now, network_message_id),
            )
            tx.execute(
                "INSERT INTO transport_attempts(network_message_id,attempt_no,outcome,error,attempted_at) VALUES (?,?,'ACKED',NULL,?)",
                (network_message_id, int(row["attempts"]), now),
            )

    def fail(self, network_message_id: str, error: str, now: str, retry_at: str, max_attempts: int) -> str:
        with self.transaction() as tx:
            row = tx.execute("SELECT * FROM transport_spool WHERE network_message_id=?", (network_message_id,)).fetchone()
            if row is None:
                raise KeyError(network_message_id)
            if row["state"] != "INFLIGHT":
                raise ValueError("only INFLIGHT packet can fail")
            attempts = int(row["attempts"])
            tx.execute(
                "INSERT INTO transport_attempts(network_message_id,attempt_no,outcome,error,attempted_at) VALUES (?,?,'FAILED',?,?)",
                (network_message_id, attempts, error, now),
            )
            if attempts >= max_attempts:
                tx.execute(
                    "UPDATE transport_spool SET state='DEAD',lease_until=NULL,updated_at=?,last_error=? WHERE network_message_id=?",
                    (now, error, network_message_id),
                )
                tx.execute(
                    """
                    INSERT OR REPLACE INTO transport_dead_letter(
                        network_message_id,event_id,payload_hash,attempts,reason,failed_at
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (network_message_id,row["event_id"],row["payload_hash"],attempts,error,now),
                )
                return "DEAD"
            tx.execute(
                """
                UPDATE transport_spool
                SET state='RETRY',lease_until=NULL,next_attempt_at=?,updated_at=?,last_error=?
                WHERE network_message_id=?
                """,
                (retry_at, now, error, network_message_id),
            )
            return "RETRY"

    def state(self, event_id: str) -> str | None:
        row = self.conn.execute("SELECT state FROM transport_spool WHERE event_id=?", (event_id,)).fetchone()
        return None if row is None else str(row["state"])

    def count_dead(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM transport_dead_letter").fetchone()[0])
