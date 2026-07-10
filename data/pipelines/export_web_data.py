import json
import sqlite3
from pathlib import Path
from typing import Optional

from data.pipelines.db import REPO_ROOT, connect
from data.pipelines.best_time import best_buy_windows

DB_PATH = REPO_ROOT / "db" / "matcha_mania.db"
WEB_DATA_DIR = REPO_ROOT / "web" / "data"

HARVEST_SEASONS_QUERY = """
    SELECT country, region, flush, flush_rank, window_description, start_month, end_month,
           quality_tier, used_for_matcha, lat, lng, notes, source_url
    FROM harvest_seasons
    ORDER BY country, flush_rank
"""

MATCHA_PRICES_QUERY = """
    SELECT store, product_name, variant_label, size_grams, price, currency, in_stock, url, region, grade, cultivar, scraped_at
    FROM matcha
    ORDER BY scraped_at DESC
"""


def _export(query: str, global_name: str, filename: str, db_path: Path, output_dir: Path) -> int:
    conn = connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(query)]
    finally:
        conn.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(f"window.{global_name} = " + json.dumps(rows, indent=2) + ";\n")
    return len(rows)


def export_harvest_seasons(db_path: Optional[Path] = None, output_dir: Optional[Path] = None) -> int:
    output_dir = output_dir or WEB_DATA_DIR
    conn = connect(db_path or DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(HARVEST_SEASONS_QUERY)]
    finally:
        conn.close()

    for row in rows:
        row["buy_windows"] = best_buy_windows(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "harvest_seasons.js"
    output_path.write_text("window.HARVEST_SEASONS = " + json.dumps(rows, indent=2) + ";\n")
    return len(rows)


def export_matcha_prices(db_path: Optional[Path] = None, output_dir: Optional[Path] = None) -> int:
    return _export(MATCHA_PRICES_QUERY, "MATCHA_PRICES", "matcha_prices.js", db_path or DB_PATH, output_dir or WEB_DATA_DIR)


if __name__ == "__main__":
    harvest_count = export_harvest_seasons()
    price_count = export_matcha_prices()
    print(f"Exported {harvest_count} harvest_seasons rows and {price_count} matcha rows to {WEB_DATA_DIR}")
