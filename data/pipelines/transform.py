import re
from datetime import datetime, timezone
from typing import Optional

SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.IGNORECASE)


def parse_size_grams(*texts: str) -> Optional[int]:
    for text in texts:
        if not text:
            continue
        match = SIZE_PATTERN.search(text)
        if match:
            return round(float(match.group(1)))
    return None


def transform_product(
    raw_product: dict,
    store: str,
    currency: str,
    url: str,
    region: Optional[str],
    grade: Optional[str] = None,
    cultivar: Optional[str] = None,
) -> list:
    """Turn a Shopify product.js payload into rows matching the matcha table schema.

    grade/cultivar are hand-curated metadata (like region) — Shopify product pages don't
    expose them in a structured, scrapable way, so they come from sources.yaml, not the
    scrape itself.
    """
    scraped_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for variant in raw_product["variants"]:
        size_grams = parse_size_grams(variant.get("title", ""), raw_product.get("title", ""))
        if size_grams is None:
            print(f"skipping variant with no parseable size: {raw_product.get('title')} / {variant.get('title')}")
            continue

        variant_title = variant.get("title")
        # size is already captured structurally in size_grams — keeping it (and any other
        # variant detail like "Tin" / "15-30 Servings") appended to the title just crowds
        # the display; it's kept separately as variant_label instead, for a notes line.
        variant_label = variant_title if variant_title and variant_title != "Default Title" else None

        rows.append({
            "store": store,
            "product_name": raw_product["title"],
            "variant_label": variant_label,
            "size_grams": size_grams,
            "price": variant["price"] / 100,
            "currency": currency,
            "in_stock": bool(variant.get("available", False)),
            "url": url,
            "region": region,
            "grade": grade,
            "cultivar": cultivar,
            "scraped_at": scraped_at,
        })
    return rows
