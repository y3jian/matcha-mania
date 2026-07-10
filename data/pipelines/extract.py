from urllib.parse import urlparse

import requests

USER_AGENT = "Mozilla/5.0"


def fetch_product(product_url: str) -> dict:
    """Fetch a Shopify product's variant/price/stock data via its .js endpoint.

    Query strings and fragments are stripped before appending .js — a URL copied from
    the address bar with a variant preselected (e.g. "...?variant=123") would otherwise
    get ".js" appended after the query string instead of the path, hitting the normal
    HTML product page rather than the JSON endpoint. The .js endpoint always returns
    every variant regardless of any variant selected in the URL, so nothing is lost by
    dropping it.
    """
    parsed = urlparse(product_url)
    js_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}.js"
    resp = requests.get(js_url, headers={"User-Agent": USER_AGENT}, timeout=10)
    resp.raise_for_status()
    return resp.json()
