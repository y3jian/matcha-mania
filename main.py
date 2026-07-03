from pathlib import Path

import yaml

from data.pipelines.extract import fetch_product
from data.pipelines.transform import transform_product
from data.pipelines.load import load_matcha_rows
from data.pipelines.export_web_data import export_matcha_prices

SOURCES_PATH = Path(__file__).resolve().parent / "db" / "config" / "sources.yaml"


def run() -> None:
    config = yaml.safe_load(SOURCES_PATH.read_text())
    all_rows = []
    for store in config["stores"]:
        for product in store["products"]:
            raw_product = fetch_product(product["url"])
            rows = transform_product(
                raw_product,
                store=store["name"],
                currency=store["currency"],
                url=product["url"],
                region=product.get("region"),
            )
            all_rows.extend(rows)
            print(f"{store['name']}: {raw_product['title']} - {len(rows)} variant(s)")

    inserted = load_matcha_rows(all_rows)
    print(f"Inserted {inserted} rows into matcha table")

    exported = export_matcha_prices()
    print(f"Exported {exported} matcha rows to web/data/matcha_prices.js")


if __name__ == "__main__":
    run()
