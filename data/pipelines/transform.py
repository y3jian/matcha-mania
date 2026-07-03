import re
from datetime import datetime, timezone
from typing import Optional

SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.IGNORECASE)


def _size_grams(*texts: str) -> Optional[int]:
    for text in texts:
        if not text:
            continue
        match = SIZE_PATTERN.search(text)
        if match:
            return round(float(match.group(1)))
    return None


def transform_product(raw_product: dict, store: str, currency: str, url: str, region: Optional[str]) -> list:
    """Turn a Shopify product.js payload into rows matching the matcha table schema."""
    scraped_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for variant in raw_product["variants"]:
        size_grams = _size_grams(variant.get("title", ""), raw_product.get("title", ""))
        if size_grams is None:
            print(f"skipping variant with no parseable size: {raw_product.get('title')} / {variant.get('title')}")
            continue

        variant_title = variant.get("title")
        product_name = raw_product["title"]
        if variant_title and variant_title != "Default Title":
            product_name = f"{product_name} ({variant_title})"

        rows.append({
            "store": store,
            "product_name": product_name,
            "size_grams": size_grams,
            "price": variant["price"] / 100,
            "currency": currency,
            "in_stock": bool(variant.get("available", False)),
            "url": url,
            "region": region,
            "scraped_at": scraped_at,
        })
    return rows
