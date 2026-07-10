import re
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with schema.sql applied.

    schema.sql is written in MySQL syntax (the intended production target);
    SQLite only assigns rowids into a primary key column when it's declared
    as `INTEGER PRIMARY KEY AUTOINCREMENT`, so that substitution happens here
    rather than in the canonical schema file.
    """
    conn = sqlite3.connect(db_path)
    schema = SCHEMA_PATH.read_text()
    schema = re.sub(r"INT AUTO_INCREMENT PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT", schema)
    conn.executescript(schema)
    _migrate(conn)
    return conn


# CREATE TABLE IF NOT EXISTS (above) only helps for tables that don't exist yet — it can't
# retroactively add columns to a `matcha` table created before grade/cultivar existed.
# Add them here, guarded by a column-existence check, so an existing database (with real
# scraped history) is upgraded in place instead of needing to be dropped and recreated.
def _migrate(conn: sqlite3.Connection) -> None:
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(matcha)")}
    for column in ("grade", "cultivar", "variant_label"):
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE matcha ADD COLUMN {column} text")
    conn.commit()
