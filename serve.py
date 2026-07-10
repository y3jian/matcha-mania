"""Local dev server: serves web/ as static files and exposes /api/track so the site's
tracking UI can actually add, edit, and remove products (a static file server alone can't
write to db/config/sources.yaml, update the database, or trigger a scrape).

    POST   /api/track   {url, store?, region?, currency?}            -> add
    PATCH  /api/track    {url, store?, region?, currency?}            -> edit (omit a
                          key to leave it unchanged; send it as null to clear it)
    DELETE /api/track   {url}                                        -> remove

    python3 serve.py [port]   # defaults to 8000
"""
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from data.pipelines.manage_sources import UNSET, TrackingError, add_source, edit_source, remove_source

WEB_ROOT = Path(__file__).resolve().parent / "web"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_POST(self):
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
            ),
            lambda title: {"ok": True, "message": f"Now tracking “{title}”."},
        )

    def do_PATCH(self):
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
            )

        self._run(edit, lambda result: {"ok": True, "message": f"Updated — now under “{result['store']}”.", "result": result})

    def do_DELETE(self):
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
        except TrackingError as exc:
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
    print("POST/PATCH/DELETE /api/track to add, edit, or remove a tracked product (used by the site's tracking UI).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
