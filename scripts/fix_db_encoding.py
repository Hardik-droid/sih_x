import sqlite3
import json

conn = sqlite3.connect("data/cases.sqlite3")
cursor = conn.cursor()

rows = cursor.execute("SELECT id, data FROM objects").fetchall()
updated = 0
for row_id, data_str in rows:
    # Check if there is any replacement character or broken symbol
    if "\ufffd" in data_str or "\\ufffd" in data_str or "  " in data_str:
        fixed = data_str.replace("\ufffd", " · ").replace("\\ufffd", " · ")
        while "  " in fixed:
            fixed = fixed.replace("  ", " ")
        cursor.execute("UPDATE objects SET data = ? WHERE id = ?", (fixed, row_id))
        updated += 1
        print(f"Updated object: {row_id}")

audit_rows = cursor.execute("SELECT seq, payload FROM audit").fetchall()
audit_updated = 0
for seq, payload in audit_rows:
    if "\ufffd" in payload or "\\ufffd" in payload:
        fixed = payload.replace("\ufffd", " · ").replace("\\ufffd", " · ")
        while "  " in fixed:
            fixed = fixed.replace("  ", " ")
        cursor.execute("UPDATE audit SET payload = ? WHERE seq = ?", (fixed, seq))
        audit_updated += 1

conn.commit()
conn.close()
print(f"Done. Updated {updated} objects, {audit_updated} audit rows.")
