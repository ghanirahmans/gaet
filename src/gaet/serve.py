"""cmd_serve — web dashboard launcher."""

import argparse
from .core import DEF_DASHBOARD_HOST, DEF_DASHBOARD_PORT, NAME, argparse, box_title, get_env_str, load_env, status_info

def cmd_serve(args: argparse.Namespace) -> None:
    """Start web dashboard."""
    env = load_env()
    port = int(get_env_str(env, "GAET_DASHBOARD_PORT", str(DEF_DASHBOARD_PORT)))
    host = get_env_str(env, "GAET_DASHBOARD_HOST", DEF_DASHBOARD_HOST)

    # CLI overrides (gaet serve --port N / --no-browser)
    if getattr(args, "port", 0):
        port = int(args.port)
    no_browser = getattr(args, "no_browser", False)

    box_title(f"{NAME} serve")
    open_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{open_host}:{port}"
    status_info(f"Starting dashboard on {url}...")

    # Import here to avoid circular imports
    from dashboard import server as srv

    if not no_browser:
        import threading
        import time
        import webbrowser

        def _open_browser():
            time.sleep(0.5)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open_browser, daemon=True).start()

    srv.serve(port=port, host=host)

# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_serve_parser(subparsers, common):
    p = subparsers.add_parser("serve", help="Start web dashboard", parents=[common])
    p.add_argument("--port", type=int, default=0, help="Custom port (default: 9191 or GAET_DASHBOARD_PORT)")
    p.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    return p


command("serve", "Start web dashboard", build=_build_serve_parser)(cmd_serve)

