"""Local dev server: serves web/ as static files and exposes the tracking + pantry APIs
that make the site interactive (a static file server alone can't write to
db/config/sources.yaml, update the database, or trigger a scrape).

    POST   /api/track        {url, store?, region?, currency?, grade?, cultivar?}  -> add
    PATCH  /api/track        {url, store?, region?, currency?, grade?, cultivar?}  -> edit
                              (omit a key to leave it unchanged; send it as null to clear it)
    DELETE /api/track        {url}                                                -> remove
    POST   /api/refresh      (no body)                                            -> rescrape
                              every tracked product and re-export the site's data

    GET    /api/pantry        -> list every pantry item with computed status
    POST   /api/pantry        {product_name, size_grams, store?, url?, grade?,
                                cultivar?, region?, acquired_date?, opened_date?, notes?}
    PATCH  /api/pantry        {id, ...any editable field}                          -> edit
    DELETE /api/pantry        {id}                                                 -> remove
    POST   /api/pantry/usage  {id, grams_used, logged_at?}                         -> log a session

    GET    /api/pantry/photos            [?pantry_item_id=]  -> list photos, newest first
    POST   /api/pantry/photos {pantry_item_id, image_data_url, caption?} -> add (image_data_url
                               is a data: URL, e.g. from FileReader.readAsDataURL in the browser)
    DELETE /api/pantry/photos {id}                                       -> remove

    python3 serve.py [port]   # defaults to 8000
"""
import base64
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import main as pipeline_main
from data.pipelines.manage_sources import UNSET, TrackingError, add_source, edit_source, remove_source
from data.pipelines.pantry import (
    PantryError,
    add_pantry_item,
    add_photo,
    edit_pantry_item,
    list_pantry_status,
    list_photos,
    log_usage,
    remove_pantry_item,
    remove_photo,
)

WEB_ROOT = Path(__file__).resolve().parent / "web"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/pantry":
            self._run(lambda: list_pantry_status(), lambda items: {"ok": True, "items": items})
            return
        if parsed.path == "/api/pantry/photos":
            query = parse_qs(parsed.query)
            item_id = int(query["pantry_item_id"][0]) if "pantry_item_id" in query else None
            self._run(lambda: list_photos(item_id), lambda photos: {"ok": True, "photos": photos})
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/refresh":
            self._refresh()
            return
        if self.path == "/api/pantry":
            self._add_pantry_item()
            return
        if self.path == "/api/pantry/usage":
            self._log_usage()
            return
        if self.path == "/api/pantry/photos":
            self._add_photo()
            return
        if self.path != "/api/track":
            self.send_error(404)
            return
        payload = self._read_json()
        if payload is None:
            return

        url = (payload.get("url") or "").strip()
        if not url:
            self._send_json(400, {"ok": False, "error": "A product URL is required."})
            return

        self._run(
            lambda: add_source(
                url,
                store=(payload.get("store") or "").strip() or None,
                region=(payload.get("region") or "").strip() or None,
                currency=(payload.get("currency") or "USD").strip() or "USD",
                grade=(payload.get("grade") or "").strip() or None,
                cultivar=(payload.get("cultivar") or "").strip() or None,
            ),
            lambda title: {"ok": True, "message": f"Now tracking “{title}”."},
        )

    def _refresh(self):
        # no fields needed, but the body must still be drained or leftover bytes could
        # corrupt the next request on a keep-alive connection
        if self._read_json() is None:
            return

        def summarize(result):
            failures = result["failures"]
            message = f"Refreshed {result['scraped']} product(s)."
            if failures:
                message += f" {len(failures)} failed: " + "; ".join(f"{f['url']} ({f['error']})" for f in failures)
            return {"ok": True, "message": message, "result": result}

        self._run(pipeline_main.run, summarize)

    def _add_pantry_item(self):
        payload = self._read_json()
        if payload is None:
            return
        product_name = (payload.get("product_name") or "").strip()
        if not product_name:
            self._send_json(400, {"ok": False, "error": "A product name is required."})
            return
        try:
            size_grams = int(payload.get("size_grams"))
        except (TypeError, ValueError):
            self._send_json(400, {"ok": False, "error": "size_grams must be a whole number."})
            return

        self._run(
            lambda: add_pantry_item(
                product_name,
                size_grams,
                store=(payload.get("store") or "").strip() or None,
                url=(payload.get("url") or "").strip() or None,
                grade=(payload.get("grade") or "").strip() or None,
                cultivar=(payload.get("cultivar") or "").strip() or None,
                region=(payload.get("region") or "").strip() or None,
                acquired_date=(payload.get("acquired_date") or "").strip() or None,
                opened_date=(payload.get("opened_date") or "").strip() or None,
                notes=(payload.get("notes") or "").strip() or None,
            ),
            lambda item_id: {"ok": True, "message": f"Added “{product_name}” to your pantry.", "id": item_id},
        )

    def _log_usage(self):
        payload = self._read_json()
        if payload is None:
            return
        try:
            item_id = int(payload.get("id"))
            grams_used = float(payload.get("grams_used"))
        except (TypeError, ValueError):
            self._send_json(400, {"ok": False, "error": "id and grams_used are required."})
            return

        self._run(
            lambda: log_usage(item_id, grams_used, logged_at=payload.get("logged_at") or None),
            lambda _: {"ok": True, "message": f"Logged {grams_used}g."},
        )

    def _add_photo(self):
        payload = self._read_json()
        if payload is None:
            return
        try:
            item_id = int(payload.get("pantry_item_id"))
        except (TypeError, ValueError):
            self._send_json(400, {"ok": False, "error": "A pantry item id is required."})
            return

        data_url = payload.get("image_data_url") or ""
        try:
            # "data:image/jpeg;base64,<...>" — the browser's FileReader.readAsDataURL() format
            _, b64_data = data_url.split(",", 1)
            image_bytes = base64.b64decode(b64_data)
        except (ValueError, base64.binascii.Error):
            self._send_json(400, {"ok": False, "error": "image_data_url must be a base64 data URL."})
            return

        self._run(
            lambda: add_photo(item_id, image_bytes, caption=(payload.get("caption") or "").strip() or None),
            lambda photo: {"ok": True, "message": "Photo added.", "photo": photo},
        )

    def do_PATCH(self):
        if self.path == "/api/pantry":
            self._edit_pantry_item()
            return
        if self.path != "/api/track":
            self.send_error(404)
            return
        payload = self._read_json()
        if payload is None:
            return

        url = (payload.get("url") or "").strip()
        if not url:
            self._send_json(400, {"ok": False, "error": "A product URL is required."})
            return

        def edit():
            return edit_source(
                url,
                store=payload["store"].strip() if "store" in payload and payload["store"] else UNSET,
                region=payload["region"] if "region" in payload else UNSET,
                currency=payload["currency"].strip() if "currency" in payload and payload["currency"] else UNSET,
                grade=payload["grade"] if "grade" in payload else UNSET,
                cultivar=payload["cultivar"] if "cultivar" in payload else UNSET,
            )

        self._run(edit, lambda result: {"ok": True, "message": f"Updated — now under “{result['store']}”.", "result": result})

    def _edit_pantry_item(self):
        payload = self._read_json()
        if payload is None:
            return
        try:
            item_id = int(payload.get("id"))
        except (TypeError, ValueError):
            self._send_json(400, {"ok": False, "error": "A pantry item id is required."})
            return

        fields = {k: v for k, v in payload.items() if k != "id"}
        self._run(lambda: edit_pantry_item(item_id, **fields), lambda _: {"ok": True, "message": "Updated."})

    def do_DELETE(self):
        if self.path == "/api/pantry":
            self._remove_pantry_item()
            return
        if self.path == "/api/pantry/photos":
            self._remove_photo()
            return
        if self.path != "/api/track":
            self.send_error(404)
            return
        payload = self._read_json()
        if payload is None:
            return

        url = (payload.get("url") or "").strip()
        if not url:
            self._send_json(400, {"ok": False, "error": "A product URL is required."})
            return

        self._run(lambda: remove_source(url), lambda store: {"ok": True, "message": f"Stopped tracking (was under “{store}”)."})

    def _remove_pantry_item(self):
        payload = self._read_json()
        if payload is None:
            return
        try:
            item_id = int(payload.get("id"))
        except (TypeError, ValueError):
            self._send_json(400, {"ok": False, "error": "A pantry item id is required."})
            return

        self._run(lambda: remove_pantry_item(item_id), lambda _: {"ok": True, "message": "Removed from pantry."})

    def _remove_photo(self):
        payload = self._read_json()
        if payload is None:
            return
        try:
            photo_id = int(payload.get("id"))
        except (TypeError, ValueError):
            self._send_json(400, {"ok": False, "error": "A photo id is required."})
            return

        self._run(lambda: remove_photo(photo_id), lambda _: {"ok": True, "message": "Photo removed."})

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "Invalid request body."})
            return None

    def _run(self, action, on_success):
        try:
            self._send_json(200, on_success(action()))
        except (TrackingError, PantryError) as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # keep the server alive even if something unexpected breaks
            self._send_json(500, {"ok": False, "error": f"Unexpected error: {exc}"})

    def _send_json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("localhost", port), Handler)
    print(f"Serving {WEB_ROOT} at http://localhost:{port}/harvest_map.html")
    print("POST/PATCH/DELETE /api/track to add, edit, or remove a tracked product.")
    print("POST /api/refresh to rescrape every tracked product (used by the site's tracking UI).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
