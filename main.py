from pathlib import Path

import requests
import yaml

from data.pipelines.extract import fetch_product
from data.pipelines.transform import transform_product
from data.pipelines.load import load_matcha_rows
from data.pipelines.export_web_data import export_matcha_prices

SOURCES_PATH = Path(__file__).resolve().parent / "db" / "config" / "sources.yaml"


def run() -> dict:
    """Scrape every tracked product, load fresh rows, and re-export the site's data.

    One store's fetch failing (a dead link, a store temporarily down, a redesign that
    broke the .js endpoint) shouldn't stop every *other* store from refreshing — each
    product is scraped independently and failures are collected rather than raised.
    """
    config = yaml.safe_load(SOURCES_PATH.read_text())
    all_rows = []
    failures = []
    for store in config["stores"]:
        for product in store["products"]:
            try:
                raw_product = fetch_product(product["url"])
            except requests.RequestException as exc:
                print(f"Failed to fetch {product['url']}: {exc}")
                failures.append({"url": product["url"], "error": str(exc)})
                continue

            rows = transform_product(
                raw_product,
                store=store["name"],
                currency=store["currency"],
                url=product["url"],
                region=product.get("region"),
                grade=product.get("grade"),
                cultivar=product.get("cultivar"),
            )
            all_rows.extend(rows)
            print(f"{store['name']}: {raw_product['title']} - {len(rows)} variant(s)")

    inserted = load_matcha_rows(all_rows)
    print(f"Inserted {inserted} rows into matcha table")

    exported = export_matcha_prices()
    print(f"Exported {exported} matcha rows to web/data/matcha_prices.js")

    return {"scraped": len(all_rows), "inserted": inserted, "exported": exported, "failures": failures}


if __name__ == "__main__":
    run()
