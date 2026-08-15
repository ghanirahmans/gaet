#!/usr/bin/env python3
"""Simple HTTP server for gaet dashboard.

Serves static HTML + provides API endpoints by calling gaet CLI.
No dependencies needed beyond stdlib.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
GAET_PY = ROOT / "gaet.py"
STATIC_DIR = Path(__file__).resolve().parent / "static"
ENV_FILE = Path(os.environ.get("HOME", "/home/ghaniyrahmans"), ".gaet", ".env")


def run_gaet(args: list[str]) -> tuple[int, str, str]:
    """Run gaet command and return (rc, stdout, stderr)."""
    import subprocess
    r = subprocess.run(
        [sys.executable, str(GAET_PY)] + args,
        capture_output=True, text=True, timeout=120
    )
    return r.returncode, r.stdout, r.stderr


class DashboardHandler(BaseHTTPRequestHandler):
    """Handle API requests and serve static files."""

    def log_message(self, format, *args):
        """Suppress default logging for cleaner output."""
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API endpoint: status
        if path == "/api/status":
            rc, out, err = run_gaet(["status", "--json"])
            if rc == 0:
                try:
                    data = json.loads(out)
                    self.send_json(200, data)
                except json.JSONDecodeError:
                    self.send_json(500, {"error": "Invalid JSON from gaet"})
            else:
                self.send_json(500, {"error": err or "Failed to get status"})
            return

        # Serve static files
        if STATIC_DIR.is_dir():
            file_path = STATIC_DIR / path.lstrip("/")
            if file_path.exists() and file_path.is_file():
                content_type = self.guess_type(path)
                with open(file_path, "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.end_headers()
                    self.wfile.write(f.read())
                return

        # Default: serve index.html
        index = STATIC_DIR / "index.html"
        if index.exists():
            with open(index, "rb") as f:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f.read())
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # API endpoint: push
        if path == "/api/push":
            auto = params.get("auto", [None])[0]
            args = ["push"]
            if auto:
                args.extend(["--auto", auto])
            rc, out, err = run_gaet(args)
            msg = "Push ke cloud selesai!" if rc == 0 else f"Push gagal: {err}"
            self.send_json(200, {"ok": rc == 0, "msg": msg})
            return

        # API endpoint: fetch
        if path == "/api/fetch":
            rc, out, err = run_gaet(["fetch", "--yes"])
            msg = "Fetch dari cloud selesai!" if rc == 0 else f"Fetch gagal: {err}"
            self.send_json(200, {"ok": rc == 0, "msg": msg})
            return

        # API endpoint: stop
        if path == "/api/stop":
            rc, out, err = run_gaet(["stop"])
            msg = "Auto-backup dihentikan" if rc == 0 else f"Gagal stop: {err}"
            self.send_json(200, {"ok": rc == 0, "msg": msg})
            return

        self.send_error(404, "Not found")

    def send_json(self, code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def guess_type(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        return types.get(ext, "application/octet-stream")


def serve(port: int = 9191, host: str = "127.0.0.1"):
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard...")
        server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9191
    serve(port=port)
