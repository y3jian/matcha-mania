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
