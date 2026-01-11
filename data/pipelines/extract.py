import requests


def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    print(resp.status_code)
    print(resp.headers.get("content-type"))
    print(resp.text[:300])

    return resp


html = fetch_html("https://kettl.co/products/kiwami-matcha?variant=44827350696186")
print(html)

with open("kettl_debug.html", "w", encoding="utf-8") as f:
    f.write(html.text)
#https://ippodotea.com/collections/matcha/products/ummon-no-mukashi-40g 