from pathlib import Path

from data.pipelines.db import REPO_ROOT, connect
from data.pipelines.export_web_data import export_harvest_seasons

DB_PATH = REPO_ROOT / "db" / "matcha_mania.db"
SEED_PATH = REPO_ROOT / "db" / "seed" / "harvest_seasons.sql"


def load_harvest_seasons(db_path: Path = DB_PATH) -> int:
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM harvest_seasons")
        conn.executescript(SEED_PATH.read_text())
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM harvest_seasons").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    row_count = load_harvest_seasons()
    print(f"Loaded {row_count} harvest_seasons rows into {DB_PATH}")
    exported = export_harvest_seasons()
    print(f"Exported {exported} harvest_seasons rows to web/data/harvest_seasons.js")
