#!/usr/bin/env python3
"""Simple HTTP server for gaet dashboard.

Serves static HTML + provides rich API endpoints by interfacing with gaet CLI.
No dependencies needed beyond Python standard library.
"""
import json
import os
import sys
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent  # ~/.local/bin
SCRIPT_DIR = Path(__file__).resolve().parent     # ~/.local/bin/dashboard
GAET_CONFIG = Path(os.environ.get("HOME", str(Path.home())), ".gaet")
ENV_FILE = GAET_CONFIG / ".env"
BACKUP_DIR = GAET_CONFIG / "backups"

# The `gaet` binary lives next to this dashboard module in the install dir
# (~/.local/bin/gaet). When run from the repo (dev mode), fall back to running gaet.py.
GAET_BIN = ROOT / "gaet"
GAET_PY = SCRIPT_DIR.parent / "gaet.py"
if not GAET_PY.is_file() and GAET_BIN.is_file():
    GAET_CMD = [sys.executable, str(GAET_BIN)]
elif GAET_PY.is_file():
    GAET_CMD = [sys.executable, str(GAET_PY)]
else:
    GAET_CMD = ["gaet"]

STATIC_DIR = SCRIPT_DIR / "static"
PUBLIC_DIR = SCRIPT_DIR / "public"


def run_gaet(args: list[str]) -> tuple[int, str, str]:
    """Run gaet command and return (rc, stdout, stderr)."""
    import subprocess
    r = subprocess.run(
        GAET_CMD + args,
        capture_output=True, text=True, timeout=120
    )
    return r.returncode, r.stdout, r.stderr


def mask_password_url(url_str: str) -> str:
    """Mask password in postgresql URL."""
    if not url_str:
        return ""
    return re.sub(r'(://[^:]+:)[^@]+(@)', r'\1••••••••\2', url_str)


def get_detected_instances() -> list[dict]:
    """Auto-detect running local PostgreSQL instances."""
    try:
        for p in [str(ROOT / "src"), str(ROOT / "gaet_pkg"), str(ROOT)]:
            if p not in sys.path and os.path.isdir(p):
                sys.path.insert(0, p)
        from gaet.detect import detect_local_pg
        from gaet.core import find_pg_tools, load_env
        env = load_env()
        tools = find_pg_tools(env)
        psql = tools.get("psql", "")
        if not psql:
            return []
        raw_list = detect_local_pg(psql)
        formatted = []
        for inst in raw_list:
            dbs = [d.strip() for d in inst.get("databases", "").split(",") if d.strip()]
            formatted.append({
                "host": inst.get("host", "127.0.0.1"),
                "port": inst.get("port", "5432"),
                "user": inst.get("user", "postgres"),
                "default_db": inst.get("default_db", "postgres"),
                "databases": dbs
            })
        return formatted
    except Exception as e:
        print(f"Detect error: {e}", file=sys.stderr)
        return []


class DashboardHandler(BaseHTTPRequestHandler):
    """Handle API requests and serve static files."""

    def log_message(self, format, *args):
        """Suppress default logging for cleaner console output."""
        pass

    def read_json_body() -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            try:
                body = self.rfile.read(content_length).decode("utf-8")
                return json.loads(body)
            except Exception:
                pass
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # ── API Endpoint: Status ─────────────────────────────────────────────
        if path == "/api/status":
            rc, out, err = run_gaet(["status", "--json"])
            if rc == 0:
                try:
                    data = json.loads(out)
                    self.send_json(200, data)
                except json.JSONDecodeError:
                    self.send_json(500, {"error": "Invalid JSON output from gaet status"})
            else:
                self.send_json(500, {"error": err or "Failed to get status"})
            return

        # ── API Endpoint: Check Diagnostic ──────────────────────────────────
        if path == "/api/check":
            rc, out, err = run_gaet(["check", "--json"])
            if rc == 0:
                try:
                    data = json.loads(out)
                    self.send_json(200, data)
                except json.JSONDecodeError:
                    self.send_json(500, {"error": "Invalid JSON output from gaet check"})
            else:
                self.send_json(500, {"error": err or "Failed to perform diagnostic check"})
            return

        # ── API Endpoint: Doctor Check ──────────────────────────────────────
        if path == "/api/doctor":
            rc, out, err = run_gaet(["doctor", "--plain"])
            self.send_json(200, {"ok": rc == 0, "output": out or err})
            return

        # ── API Endpoint: Diff Analysis ─────────────────────────────────────
        if path == "/api/diff":
            rc, out, err = run_gaet(["diff", "--plain"])
            self.send_json(200, {"ok": rc == 0, "output": out or err})
            return

        # ── API Endpoint: Test Remote Connection ────────────────────────────
        if path == "/api/remote/test":
            rc, out, err = run_gaet(["remote", "--plain"])
            self.send_json(200, {"ok": rc == 0, "output": out or err, "connected": "Testing remote cloud connection... OK" in (out or "")})
            return

        # ── API Endpoint: Export Shell Env ──────────────────────────────────
        if path == "/api/export":
            rc, out, err = run_gaet(["export"])
            self.send_json(200, {"ok": rc == 0, "env_vars": out or err})
            return

        # ── API Endpoint: Detect Local PostgreSQL ───────────────────────────
        if path == "/api/detect":
            instances = get_detected_instances()
            self.send_json(200, {"ok": True, "instances": instances})
            return

        # ── API Endpoint: Snapshots ──────────────────────────────────────────
        if path == "/api/snapshots":
            rc, out, err = run_gaet(["snapshots", "--json"])
            if rc == 0:
                try:
                    data = json.loads(out)
                    self.send_json(200, data)
                except json.JSONDecodeError:
                    self.send_json(500, {"error": "Invalid JSON output from gaet snapshots"})
            else:
                self.send_json(500, {"error": err or "Failed to get snapshots list"})
            return

        # ── API Endpoint: Logs Viewer ───────────────────────────────────────
        if path == "/api/logs":
            log_lines = []
            log_files = [BACKUP_DIR / "cron.log", BACKUP_DIR / "gaet.log"]
            for lf in log_files:
                if lf.is_file():
                    try:
                        with open(lf, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            log_lines.extend(lines[-100:])
                    except OSError:
                        pass
            self.send_json(200, {"logs": log_lines[-100:] if log_lines else ["No log entries found."]})
            return

        # ── API Endpoint: Config GET ────────────────────────────────────────
        if path == "/api/config":
            config_vars = {}
            if ENV_FILE.is_file():
                try:
                    with open(ENV_FILE, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                config_vars[k.strip()] = v.strip()
                except OSError:
                    pass

            masked_config = dict(config_vars)
            for k, v in masked_config.items():
                if "URL" in k or "PASS" in k or "SECRET" in k:
                    if "://" in v:
                        masked_config[k] = mask_password_url(v)
                    elif v:
                        masked_config[k] = "••••••••"

            self.send_json(200, {
                "config": config_vars,
                "masked_config": masked_config,
                "env_file": str(ENV_FILE)
            })
            return

        # ── API Endpoint: Snapshot Download ────────────────────────────────
        if path == "/api/snapshots/download":
            filename = params.get("file", [None])[0]
            if not filename or ".." in filename or "/" in filename or "\\" in filename:
                self.send_json(400, {"error": "Invalid filename requested"})
                return

            file_path = BACKUP_DIR / filename
            if file_path.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(file_path.stat().st_size))
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_json(404, {"error": f"Snapshot file '{filename}' not found"})
                return

        # ── Serve Static & Public Files ─────────────────────────────────────
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

        if PUBLIC_DIR.is_dir():
            pub_path = PUBLIC_DIR / path.lstrip("/")
            if pub_path.exists() and pub_path.is_file():
                content_type = self.guess_type(path)
                with open(pub_path, "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.end_headers()
                    self.wfile.write(f.read())
                return

        # Default fallback: serve index.html
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

        # Read JSON body if available
        content_length = int(self.headers.get("Content-Length", 0))
        body_data = {}
        if content_length > 0:
            try:
                body_raw = self.rfile.read(content_length).decode("utf-8")
                body_data = json.loads(body_raw)
            except Exception:
                pass

        # ── API Endpoint: Push ──────────────────────────────────────────────
        if path == "/api/push":
            auto = params.get("auto", [None])[0] or body_data.get("auto")
            dry_run = body_data.get("dry_run", False) or params.get("dry_run", [False])[0]
            args = ["push"]
            if dry_run:
                args.append("--dry-run")
            elif auto:
                args.extend(["--auto", str(auto)])
            rc, out, err = run_gaet(args)
            msg = "Push dry-run completed!" if dry_run else ("Cloud push complete!" if rc == 0 else f"Push failed: {err or out}")
            self.send_json(200, {"ok": rc == 0, "msg": msg, "output": out})
            return

        # ── API Endpoint: Fetch ─────────────────────────────────────────────
        if path == "/api/fetch":
            rc, out, err = run_gaet(["fetch", "--yes"])
            msg = "Cloud fetch complete!" if rc == 0 else f"Fetch failed: {err or out}"
            self.send_json(200, {"ok": rc == 0, "msg": msg, "output": out})
            return

        # ── API Endpoint: Restore Snapshot ────────────────────────────────
        if path == "/api/restore":
            filename = params.get("file", [None])[0] or body_data.get("filename") or body_data.get("file")
            if not filename:
                self.send_json(400, {"ok": False, "msg": "Missing filename parameter"})
                return
            rc, out, err = run_gaet(["restore", filename, "--yes"])
            msg = f"Restored from '{filename}' successfully!" if rc == 0 else f"Restore failed: {err or out}"
            self.send_json(200, {"ok": rc == 0, "msg": msg, "output": out})
            return

        # ── API Endpoint: Delete Snapshot ─────────────────────────────────
        if path == "/api/snapshots/delete":
            filename = params.get("file", [None])[0] or body_data.get("filename") or body_data.get("file")
            if not filename or ".." in filename or "/" in filename or "\\" in filename:
                self.send_json(400, {"ok": False, "msg": "Invalid filename requested"})
                return

            file_path = BACKUP_DIR / filename
            if file_path.is_file():
                try:
                    file_path.unlink()
                    self.send_json(200, {"ok": True, "msg": f"Snapshot '{filename}' deleted successfully."})
                except OSError as e:
                    self.send_json(500, {"ok": False, "msg": f"Failed to delete snapshot: {e}"})
            else:
                self.send_json(404, {"ok": False, "msg": f"Snapshot file '{filename}' not found"})
            return

        # ── API Endpoint: Config POST (Update .env) ───────────────────────
        if path == "/api/config":
            new_vars = body_data.get("config", {})
            if not isinstance(new_vars, dict) or not new_vars:
                self.send_json(400, {"ok": False, "msg": "No configuration parameters provided"})
                return

            existing = {}
            if ENV_FILE.is_file():
                try:
                    with open(ENV_FILE, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                existing[k.strip()] = v.strip()
                except OSError:
                    pass

            for k, v in new_vars.items():
                if v != "********" and v != "":
                    existing[k] = str(v)

            lines = ["# gaet configuration\n"]
            for k, v in existing.items():
                lines.append(f"{k}={v}\n")

            try:
                GAET_CONFIG.mkdir(parents=True, exist_ok=True)
                with open(ENV_FILE, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                os.chmod(str(ENV_FILE), 0o600) if sys.platform != "win32" else None
                self.send_json(200, {"ok": True, "msg": "Configuration updated successfully!"})
            except OSError as e:
                self.send_json(500, {"ok": False, "msg": f"Failed to save configuration: {e}"})
            return

        # ── API Endpoint: Stop Auto-Backup ─────────────────────────────────
        if path == "/api/stop":
            rc, out, err = run_gaet(["stop"])
            msg = "Auto-backup timer stopped successfully!" if rc == 0 else f"Failed to stop scheduler: {err or out}"
            self.send_json(200, {"ok": rc == 0, "msg": msg, "output": out})
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
