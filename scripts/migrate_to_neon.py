"""
Migrate all forensic cases, objects, and audit hash chains
from local SQLite (data/cases.sqlite3) to Neon Serverless PostgreSQL.
"""
import os
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure SIH root is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import psycopg2
from psycopg2.extras import DictCursor
from core.store import Store


def migrate():
    sqlite_path = ROOT / "data" / "cases.sqlite3"
    if not sqlite_path.exists():
        print(f"[-] SQLite database not found at {sqlite_path}")
        return

    neon_url = os.environ.get("DATABASE_URL")
    if not neon_url:
        print("[-] DATABASE_URL not set in environment or .env")
        return

    print(f"[*] Connecting to source SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    print(f"[*] Connecting to destination Neon PostgreSQL: {neon_url.split('@')[-1]}")
    pg_conn = psycopg2.connect(neon_url)

    # 1. Initialize destination schema
    with pg_conn.cursor() as cur:
        cur.execute("""
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
    pg_conn.commit()

    # 2. Migrate objects
    objects = sqlite_conn.execute("SELECT id, kind, case_id, data FROM objects ORDER BY rowid").fetchall()
    print(f"[*] Found {len(objects)} objects in SQLite.")

    with pg_conn.cursor() as cur:
        for obj in objects:
            cur.execute("""
            INSERT INTO objects (id, kind, case_id, data)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data
            """, (obj["id"], obj["kind"], obj["case_id"], obj["data"]))
    pg_conn.commit()
    print(f"[+] Successfully migrated {len(objects)} objects to Neon DB.")

    # 3. Migrate audit log with exact sequences preserved
    audit_rows = sqlite_conn.execute("SELECT seq, case_id, payload, previous_hash, hash FROM audit ORDER BY seq").fetchall()
    print(f"[*] Found {len(audit_rows)} audit records in SQLite.")

    with pg_conn.cursor() as cur:
        for row in audit_rows:
            cur.execute("""
            INSERT INTO audit (seq, case_id, payload, previous_hash, hash)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (seq) DO UPDATE SET
                case_id = EXCLUDED.case_id,
                payload = EXCLUDED.payload,
                previous_hash = EXCLUDED.previous_hash,
                hash = EXCLUDED.hash
            """, (row["seq"], row["case_id"], row["payload"], row["previous_hash"], row["hash"]))

        # Reset Postgres sequence to continue after the max seq
        if audit_rows:
            cur.execute("SELECT setval(pg_get_serial_sequence('audit', 'seq'), COALESCE((SELECT MAX(seq) FROM audit), 1))")
    pg_conn.commit()
    print(f"[+] Successfully migrated {len(audit_rows)} audit logs to Neon DB.")

    # 4. Verify integrity in Neon using Store
    print("[*] Verifying integrity with Store...")
    store = Store(database_url=neon_url)
    cases = store.list("case")
    print(f"[+] Total forensic cases in Neon: {len(cases)}")
    for c in cases:
        audit_info = store.audit_log(c["id"])
        print(f"    - Case '{c.get('name', c['id'])}' (ID: {c['id']}): Audit Valid = {audit_info['valid']} ({len(audit_info['events'])} events)")
        if not audit_info["valid"]:
            print(f"      [!] Warning: Audit chain mismatch in case {c['id']}")

    sqlite_conn.close()
    pg_conn.close()
    print("\n[SUCCESS] Migration to Neon DB completed successfully!")


if __name__ == "__main__":
    migrate()
