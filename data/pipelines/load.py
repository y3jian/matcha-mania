from pathlib import Path

from data.pipelines.db import REPO_ROOT, connect

DB_PATH = REPO_ROOT / "db" / "matcha_mania.db"


def load_matcha_rows(rows: list, db_path: Path = DB_PATH) -> int:
    conn = connect(db_path)
    try:
        conn.executemany(
            """
            INSERT INTO matcha (store, product_name, size_grams, price, currency, in_stock, url, region, scraped_at)
            VALUES (:store, :product_name, :size_grams, :price, :currency, :in_stock, :url, :region, :scraped_at)
            """,
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


# Columns update_matcha_rows() is allowed to write — kept as a fixed allowlist since the
# column names get interpolated into the SQL string (values are still bound as parameters).
_UPDATABLE_COLUMNS = {"store", "region", "currency"}


def update_matcha_rows(url: str, db_path: Path = DB_PATH, **fields) -> int:
    """Update store/region/currency on every existing row for this URL — used when editing
    a tracked product's metadata, so already-scraped rows reflect the correction immediately
    rather than waiting for the next scrape."""
    unknown = set(fields) - _UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"Not updatable: {sorted(unknown)}")
    if not fields:
        return 0

    conn = connect(db_path)
    try:
        set_clause = ", ".join(f"{column} = :{column}" for column in fields)
        params = {**fields, "url": url}
        cur = conn.execute(f"UPDATE matcha SET {set_clause} WHERE url = :url", params)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_matcha_rows(url: str, db_path: Path = DB_PATH) -> int:
    """Delete every row for this URL — used when a product is removed from tracking."""
    conn = connect(db_path)
    try:
        cur = conn.execute("DELETE FROM matcha WHERE url = :url", {"url": url})
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
