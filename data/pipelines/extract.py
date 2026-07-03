import requests

USER_AGENT = "Mozilla/5.0"


def fetch_product(product_url: str) -> dict:
    """Fetch a Shopify product's variant/price/stock data via its .js endpoint."""
    js_url = product_url.rstrip("/") + ".js"
    resp = requests.get(js_url, headers={"User-Agent": USER_AGENT}, timeout=10)
    resp.raise_for_status()
    return resp.json()
