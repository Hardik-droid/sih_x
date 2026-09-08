"""Compute and attach FQI quality metrics and companion audio info to all case artifacts."""
import json
import sqlite3
from pathlib import Path
from core.quality import assess_video_file

DB_PATH = Path("data/cases.sqlite3")
CASE_ID = "1de6799a1820474c876ec10af6aa20db"


def main():
    db = sqlite3.connect(DB_PATH)
    rows = db.execute("SELECT id, data FROM objects WHERE case_id=? AND kind='artifact'", (CASE_ID,)).fetchall()
    print(f"Assessing {len(rows)} artifacts for case {CASE_ID}...")
    updated = 0
    for art_id, raw in rows:
        art = json.loads(raw)
        preview = art.get("preview_path")
        if preview and Path(preview).exists():
            q = assess_video_file(preview)
            art["quality_score"] = q["forensic_quality_index"]
            art["quality_category"] = q["category"]
            art["quality_metrics"] = q
            db.execute("UPDATE objects SET data=? WHERE id=?", (json.dumps(art), art_id))
            updated += 1
            print(f"[{updated:02d}/{len(rows):02d}] {art.get('name')}: FQI={q['forensic_quality_index']} ({q['category']}) | Blur={q['blur_variance']} | Blockiness={q['blockiness']}")
        else:
            print(f"Skipping {art.get('name')}, no preview at {preview}")

    db.commit()
    db.close()
    print(f"\nFinished: {updated} artifacts updated with Forensic Quality Index scores.")


if __name__ == "__main__":
    main()
