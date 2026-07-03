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
    return conn
