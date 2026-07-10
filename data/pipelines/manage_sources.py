"""Add, edit, and remove tracked products in db/config/sources.yaml.

All writes edit the file's text directly (rather than a full parse-and-dump round trip)
so the existing hand-written comments and formatting in sources.yaml are left untouched —
see _store_blocks()/_splice() for why a full YAML dump isn't safe here.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
import yaml

from data.pipelines.extract import fetch_product
from data.pipelines.transform import parse_size_grams, transform_product
from data.pipelines.load import delete_matcha_rows, load_matcha_rows, update_matcha_rows
from data.pipelines.export_web_data import export_matcha_prices

SOURCES_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "config" / "sources.yaml"

# sentinel so edit_source() can tell "leave this field alone" apart from "set it to None/empty"
UNSET = object()


class TrackingError(Exception):
    """Raised for any user-facing failure (bad URL, unsupported store, no parseable size,
    unknown product, name collision, etc.) — callers other than the CLI (e.g. a request
    handler) need this instead of SystemExit, which would tear down the whole process."""


# Matches a top-level store entry, e.g. '  - name: Kettl' or '  - name: "Rocky\'s Matcha"'.
STORE_HEADER_RE = re.compile(r'^  - name: (.+)$', re.MULTILINE)
CURRENCY_LINE_RE = re.compile(r'^    currency: .+$', re.MULTILINE)
PRODUCT_URL_RE = re.compile(r'^      - url: (.+)$', re.MULTILINE)

# per-product fields, keyed by name for _set_product_field()
PRODUCT_FIELDS = ("region", "grade", "cultivar")


def _unquote_yaml_scalar(raw: str) -> str:
    return yaml.safe_load(f"v: {raw}")["v"]


def _yaml_scalar(value) -> str:
    """Render a value as a plain YAML scalar when that round-trips safely, else quote it.

    Keeps hand-written entries (unquoted URLs, 'Fukuoka (Yame)', etc.) and generated ones
    in the same style, only falling back to JSON-style quoting (a valid YAML subset) for
    values that would otherwise be misread (e.g. containing ': ', or looking like a number).
    """
    candidate = str(value)
    if candidate and candidate.strip() == candidate:
        try:
            if yaml.safe_load(f"v: {candidate}")["v"] == candidate:
                return candidate
        except yaml.YAMLError:
            pass
    return json.dumps(candidate)


def _store_blocks(text: str):
    """Return (name, start, end) for each top-level store block, in file order.

    `end` is the offset where the next store's header begins, or — for the last store —
    where a trailing top-level '# ...' comment block begins, or end-of-file.
    """
    headers = list(STORE_HEADER_RE.finditer(text))
    blocks = []
    for i, header in enumerate(headers):
        name = _unquote_yaml_scalar(header.group(1))
        start = header.start()
        if i + 1 < len(headers):
            end = headers[i + 1].start()
        else:
            tail_comment = re.search(r"^#", text[start:], re.MULTILINE)
            end = start + tail_comment.start() if tail_comment else len(text)
        blocks.append((name, start, end))
    return blocks


def _find_product(text: str, url: str) -> Optional[dict]:
    """Locate a tracked product by URL. Returns store name plus byte spans for both the
    product's own block and its containing store's block, or None if not tracked."""
    for name, store_start, store_end in _store_blocks(text):
        matches = list(PRODUCT_URL_RE.finditer(text, store_start, store_end))
        for i, m in enumerate(matches):
            if _unquote_yaml_scalar(m.group(1)) != url:
                continue
            product_start = m.start()
            product_end = matches[i + 1].start() if i + 1 < len(matches) else store_end
            return {
                "store_name": name,
                "store_start": store_start,
                "store_end": store_end,
                "product_start": product_start,
                "product_end": product_end,
                "is_only_product": len(matches) == 1,
            }
    return None


def _splice(text: str, insert_at: int, block_text: str, blank_line_before: bool) -> str:
    """Insert `block_text` right after the last non-blank content before `insert_at`,
    preserving whatever blank-line spacing already followed it."""
    trimmed_end = len(text[:insert_at].rstrip())
    separator = "\n\n" if blank_line_before else "\n"
    return text[:trimmed_end] + separator + block_text.rstrip("\n") + text[trimmed_end:]


def _remove_span(text: str, start: int, end: int, blank_line_between: bool) -> str:
    """Remove text[start:end] (a span previously found via _store_blocks/_find_product),
    collapsing any resulting blank-line duplication so exactly one blank line remains
    between whatever's now adjacent — mirrors _splice()'s spacing convention in reverse."""
    before = text[:start].rstrip()
    after = text[end:].lstrip("\n")
    if not before:
        return after
    if not after:
        return before + "\n"
    return before + ("\n\n" if blank_line_between else "\n") + after


def _set_product_field(text: str, product_start: int, product_end: int, field: str, value: Optional[str]) -> str:
    """Set a `field: value` line within a product's own span — replacing it in place if
    already present, or appending it after the product's last existing line if not.

    Appending-if-missing matters because grade/cultivar postdate this config format: most
    existing entries only have url+region, so editing one to add a grade for the first
    time has nothing to replace yet.
    """
    value_repr = "null" if value is None else _yaml_scalar(value)
    line_re = re.compile(rf'^        {re.escape(field)}: .*$', re.MULTILINE)
    m = line_re.search(text, product_start, product_end)
    if m:
        return text[:m.start()] + f"        {field}: {value_repr}" + text[m.end():]
    trimmed_end = product_start + len(text[product_start:product_end].rstrip())
    return text[:trimmed_end] + f"\n        {field}: {value_repr}" + text[trimmed_end:]


def _render_product(url: str, region: Optional[str], grade: Optional[str], cultivar: Optional[str], indent: str) -> str:
    lines = [f"{indent}- url: {_yaml_scalar(url)}\n"]
    for field, value in (("region", region), ("grade", grade), ("cultivar", cultivar)):
        value_repr = "null" if value is None else _yaml_scalar(value)
        lines.append(f"{indent}  {field}: {value_repr}\n")
    return "".join(lines)


def _render_store(name: str, currency: str, url: str, region: Optional[str], grade: Optional[str], cultivar: Optional[str]) -> str:
    return (
        f"  - name: {_yaml_scalar(name)}\n"
        f"    currency: {_yaml_scalar(currency)}\n"
        f"    products:\n"
        f"{_render_product(url, region, grade, cultivar, '      ')}"
    )


def _default_store_name(url: str, raw_product: dict) -> str:
    vendor = (raw_product.get("vendor") or "").strip()
    if vendor:
        return vendor
    return urlparse(url).netloc.removeprefix("www.")


def add_source(
    url: str,
    store: Optional[str] = None,
    region: Optional[str] = None,
    currency: str = "USD",
    grade: Optional[str] = None,
    cultivar: Optional[str] = None,
) -> str:
    """Validate a Shopify product URL, add it to db/config/sources.yaml, scrape it once,
    and export the refreshed price data so it shows up on the site immediately.

    grade/cultivar are hand-entered, not scraped (Shopify pages don't expose them in a
    structured way) — pass them along if you know them; they power the "similar matcha"
    recommendations elsewhere.

    Returns the product's title. Raises TrackingError for any user-facing failure.
    """
    # normalize away query strings/fragments (e.g. a URL copied with "?variant=..." from a
    # specific size selected on the page) — every variant is scraped from one product URL
    # regardless, so a variant-specific query string stored as the "canonical" URL is just
    # misleading, not functional; stripping it here also means a plain and a variant-tagged
    # copy of the same link are correctly recognized as the same product below
    parsed = urlparse(url)
    url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"

    text = SOURCES_PATH.read_text()
    config = yaml.safe_load(text)

    for existing_store in config["stores"]:
        for product in existing_store["products"]:
            if product["url"] == url:
                raise TrackingError(f"Already tracking this URL under {existing_store['name']!r} — nothing to do.")

    try:
        raw_product = fetch_product(url)
    except requests.RequestException as exc:
        raise TrackingError(
            f"Couldn't fetch {url} as a Shopify product ({exc}). This pipeline only supports "
            "Shopify-backed stores (it reads the storefront's <url>.js endpoint) — check the "
            "URL is a real product page on a Shopify store."
        ) from exc

    if "variants" not in raw_product:
        raise TrackingError(f"{url} didn't return a Shopify product payload — this doesn't look like a Shopify product page.")

    sizes = [parse_size_grams(v.get("title", ""), raw_product.get("title", "")) for v in raw_product["variants"]]
    if not any(sizes):
        raise TrackingError(
            f"'{raw_product.get('title')}' has no variant with a parseable gram size (e.g. '30g') "
            "in its title, so the pipeline can't derive size_grams for it and won't produce usable "
            "price rows. Not adding it."
        )

    store_name = store or _default_store_name(url, raw_product)
    existing_config_store = next((s for s in config["stores"] if s["name"] == store_name), None)
    if existing_config_store:
        currency = existing_config_store["currency"]  # an existing store's currency always wins over the default/flag

    blocks = _store_blocks(text)
    target = next((b for b in blocks if b[0] == store_name), None)

    if target:
        _, _, end = target
        new_text = _splice(text, end, _render_product(url, region, grade, cultivar, "      "), blank_line_before=False)
    else:
        last_end = blocks[-1][2] if blocks else len(text)
        new_text = _splice(text, last_end, _render_store(store_name, currency, url, region, grade, cultivar), blank_line_before=True)

    yaml.safe_load(new_text)  # validate before writing — never leave a broken config file on disk
    SOURCES_PATH.write_text(new_text)

    rows = transform_product(raw_product, store=store_name, currency=currency, url=url, region=region, grade=grade, cultivar=cultivar)
    load_matcha_rows(rows)
    export_matcha_prices()

    return raw_product.get("title")


def edit_source(url: str, store=UNSET, region=UNSET, currency=UNSET, grade=UNSET, cultivar=UNSET) -> dict:
    """Edit an already-tracked product. `region`/`grade`/`cultivar` are per-product;
    `store`/`currency` are store-level and apply to every product under that store. Pass
    UNSET (the default) for any field you don't want to change; pass e.g. region=None to
    clear a per-product field.

    Already-scraped rows in the database are updated immediately (not just the config)
    so the site reflects the correction without waiting for the next scrape.
    Returns the product's final {"store", "currency", "region", "grade", "cultivar"}.
    Raises TrackingError if the URL isn't tracked, or a store rename would collide with
    an existing store.
    """
    text = SOURCES_PATH.read_text()
    found = _find_product(text, url)
    if not found:
        raise TrackingError(f"Not tracking {url!r} — nothing to edit.")

    config = yaml.safe_load(text)
    old_store_name = found["store_name"]

    if store is not UNSET and store and store != old_store_name:
        if any(s["name"] == store for s in config["stores"]):
            raise TrackingError(
                f"A store named {store!r} already exists — renaming into it would merge two "
                "stores' products, which isn't supported. Pick a different name, or remove "
                "and re-add this product under the existing store instead."
            )
        m = STORE_HEADER_RE.search(text, found["store_start"], found["store_end"])
        text = text[:m.start()] + f"  - name: {_yaml_scalar(store)}" + text[m.end():]
        found = _find_product(text, url)

    if currency is not UNSET and currency:
        m = CURRENCY_LINE_RE.search(text, found["store_start"], found["store_end"])
        text = text[:m.start()] + f"    currency: {_yaml_scalar(currency)}" + text[m.end():]
        found = _find_product(text, url)

    per_product_fields = {"region": region, "grade": grade, "cultivar": cultivar}
    for field, value in per_product_fields.items():
        if value is UNSET:
            continue
        text = _set_product_field(text, found["product_start"], found["product_end"], field, value)
        found = _find_product(text, url)

    new_config = yaml.safe_load(text)  # validates the edit and doubles as the source of truth below
    SOURCES_PATH.write_text(text)

    final_store = next(s for s in new_config["stores"] if any(p["url"] == url for p in s["products"]))
    final_product = next(p for p in final_store["products"] if p["url"] == url)

    changed_db_fields = {}
    if final_store["name"] != old_store_name:
        changed_db_fields["store"] = final_store["name"]
    if currency is not UNSET and currency:
        changed_db_fields["currency"] = final_store["currency"]
    for field, value in per_product_fields.items():
        if value is not UNSET:
            changed_db_fields[field] = final_product.get(field)
    if changed_db_fields:
        update_matcha_rows(url, **changed_db_fields)
        export_matcha_prices()

    return {
        "store": final_store["name"],
        "currency": final_store["currency"],
        "region": final_product.get("region"),
        "grade": final_product.get("grade"),
        "cultivar": final_product.get("cultivar"),
    }


def remove_source(url: str) -> str:
    """Stop tracking a product: remove it from sources.yaml (and, if it was the store's
    only product, the whole store block), delete its rows from the database, and
    re-export. Returns the store name it was removed from. Raises TrackingError if the
    URL isn't currently tracked."""
    text = SOURCES_PATH.read_text()
    found = _find_product(text, url)
    if not found:
        raise TrackingError(f"Not tracking {url!r} — nothing to remove.")

    if found["is_only_product"]:
        new_text = _remove_span(text, found["store_start"], found["store_end"], blank_line_between=True)
    else:
        new_text = _remove_span(text, found["product_start"], found["product_end"], blank_line_between=False)

    yaml.safe_load(new_text)
    SOURCES_PATH.write_text(new_text)

    delete_matcha_rows(url)
    export_matcha_prices()

    return found["store_name"]


def _add_command(args) -> None:
    title = add_source(args.url, store=args.store, region=args.region, currency=args.currency, grade=args.grade, cultivar=args.cultivar)
    print(f"Added '{title}' and refreshed web/data/matcha_prices.js.")


def _edit_command(args) -> None:
    result = edit_source(
        args.url,
        store=args.store if args.store is not None else UNSET,
        region=args.region if args.region is not None else UNSET,
        currency=args.currency if args.currency is not None else UNSET,
        grade=args.grade if args.grade is not None else UNSET,
        cultivar=args.cultivar if args.cultivar is not None else UNSET,
    )
    print(f"Updated {args.url} -> {result} and refreshed web/data/matcha_prices.js.")


def _remove_command(args) -> None:
    store_name = remove_source(args.url)
    print(f"Removed {args.url} (was under {store_name!r}) and refreshed web/data/matcha_prices.js.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage tracked matcha products (Shopify stores only).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Track a new product")
    add_parser.add_argument("url", help="Product page URL, e.g. https://kettl.co/products/kiwami-matcha")
    add_parser.add_argument("--store", help="Store display name (defaults to the Shopify vendor field)")
    add_parser.add_argument("--region", help="Harvest region label, e.g. 'Kyoto (Uji)' (optional)")
    add_parser.add_argument("--currency", default="USD", help="Currency code, only used if this is a new store (default: USD)")
    add_parser.add_argument("--grade", help="Grade label, e.g. 'ceremonial' (optional, hand-entered)")
    add_parser.add_argument("--cultivar", help="Cultivar, e.g. 'Samidori' (optional, hand-entered)")
    add_parser.set_defaults(func=_add_command)

    edit_parser = subparsers.add_parser("edit", help="Edit an already-tracked product's store/region/currency/grade/cultivar")
    edit_parser.add_argument("url", help="URL of the already-tracked product to edit")
    edit_parser.add_argument("--store", help="Rename the store (applies to all its products)")
    edit_parser.add_argument("--region", help="Set this product's harvest region")
    edit_parser.add_argument("--currency", help="Change the store's currency (applies to all its products)")
    edit_parser.add_argument("--grade", help="Set this product's grade")
    edit_parser.add_argument("--cultivar", help="Set this product's cultivar")
    edit_parser.set_defaults(func=_edit_command)

    remove_parser = subparsers.add_parser("remove", help="Stop tracking a product")
    remove_parser.add_argument("url", help="URL of the already-tracked product to remove")
    remove_parser.set_defaults(func=_remove_command)

    args = parser.parse_args()
    try:
        args.func(args)
    except TrackingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
