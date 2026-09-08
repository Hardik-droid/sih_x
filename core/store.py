import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import DictCursor
    HAS_PG = True
except ImportError:
    HAS_PG = False


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class PgConnectionContext:
    def __init__(self, pool_obj):
        self.pool = pool_obj
        self.conn = self.pool.getconn()

    def __enter__(self):
        if self.conn.closed:
            self.conn = self.pool.getconn()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        except Exception:
            pass
        finally:
            try:
                self.pool.putconn(self.conn)
            except Exception:
                pass

    def execute(self, sql, params=()):
        clean = sql.strip()
        if clean.upper().startswith("BEGIN"):
            return self
        pg_sql = sql.replace("?", "%s")
        if "ORDER BY rowid" in pg_sql:
            pg_sql = pg_sql.replace("ORDER BY rowid", "ORDER BY seq")
        cur = self.conn.cursor(cursor_factory=DictCursor)
        cur.execute(pg_sql, params)
        return cur

    def executescript(self, sql):
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur


class Store:
    def __init__(self, root=None, database_url=None):
        self.root = Path(root).resolve() if root else Path("data").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

        url = database_url if database_url is not None else os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
        if url and ("pytest" in sys.modules or (root and "pytest" in str(root).lower())) and database_url is None:
            url = None

        self.database_url = url
        self.is_postgres = bool(HAS_PG and self.database_url and (self.database_url.startswith("postgres://") or self.database_url.startswith("postgresql://")))
        self._pool = None

        if self.is_postgres:
            conn_url = self.database_url
            if conn_url.startswith("postgres://"):
                conn_url = "postgresql://" + conn_url[len("postgres://"):]
            self.database_url = conn_url
            self._pool = pool.ThreadedConnectionPool(1, 10, self.database_url)
            with self.connect() as db:
                db.execute("""
                CREATE TABLE IF NOT EXISTS objects (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    case_id TEXT,
                    data TEXT NOT NULL,
                    seq BIGSERIAL
                );
                CREATE INDEX IF NOT EXISTS objects_case ON objects(case_id, kind);
                CREATE TABLE IF NOT EXISTS audit (
                    seq BIGSERIAL PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS audit_case ON audit(case_id, seq);
                """)
        else:
            self.db = self.root / "cases.sqlite3"
            with self.connect() as db:
                db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS objects (id TEXT PRIMARY KEY, kind TEXT NOT NULL, case_id TEXT, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS objects_case ON objects(case_id, kind);
                CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS audit_case ON audit(case_id, seq);
                """)

    @property
    def backend(self):
        return "neon_postgres" if self.is_postgres else "sqlite"

    def connect(self):
        if self.is_postgres:
            return PgConnectionContext(self._pool)
        db = sqlite3.connect(self.db, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def put(self, kind, value, action=None, actor="system"):
        value = {"id": uid(), "created_at": now(), **value}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT kind FROM objects WHERE id=?", (value["id"],)).fetchone()
            if previous and previous[0] != kind:
                raise ValueError("An object ID cannot be reused across evidence entity types")
            db.execute("INSERT INTO objects (id, kind, case_id, data) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (value["id"], kind, value.get("case_id"), canonical(value)))
            if action:
                self._audit(db, value.get("case_id", value["id"]), actor, action, {"object_id": value["id"], "output_hash": value.get("sha256"), "status": value.get("status")})
        return value

    def get(self, object_id, kind=None):
        with self.connect() as db:
            row = db.execute("SELECT kind,data FROM objects WHERE id=?", (object_id,)).fetchone()
        if not row or (kind and row["kind"] != kind):
            raise KeyError("Record not found")
        return json.loads(row["data"])

    def list(self, kind, case_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT data FROM objects WHERE kind=?" + (" AND case_id=?" if case_id else "") + " ORDER BY rowid", (kind, case_id) if case_id else (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def _audit(self, db, case_id, actor, action, details):
        previous = db.execute("SELECT hash FROM audit WHERE case_id=? ORDER BY seq DESC LIMIT 1", (case_id,)).fetchone()
        previous = previous[0] if previous else "0" * 64
        payload = canonical({"timestamp": now(), "actor": actor, "action": action, "details": details})
        digest = hashlib.sha256((previous + payload).encode()).hexdigest()
        db.execute("INSERT INTO audit(case_id,payload,previous_hash,hash) VALUES (?,?,?,?)", (case_id, payload, previous, digest))

    def audit(self, case_id, actor, action, details):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._audit(db, case_id, actor, action, details)

    def audit_log(self, case_id):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM audit WHERE case_id=? ORDER BY seq", (case_id,)).fetchall()
        previous, events, valid = "0" * 64, [], True
        for row in rows:
            expected = hashlib.sha256((previous + row["payload"]).encode()).hexdigest()
            valid = valid and row["previous_hash"] == previous and row["hash"] == expected
            previous = row["hash"]
            events.append({"seq": row["seq"], **json.loads(row["payload"]), "previous_hash": row["previous_hash"], "hash": row["hash"]})
        return {"valid": valid, "head_hash": previous, "events": events, "limitation": "Local hash chain detects edits; export and independently retain its head to detect full rewrite or tail deletion."}
