"""Local PostgreSQL instance detection (socket + TCP fallback)."""

import os
from typing import Dict, List
from .core import Dict, List, _find_socket_paths, _socket_port, getpass, os, run_cmd

def detect_local_pg(psql_path: str) -> List[Dict[str, str]]:
    """
    Auto-detect running PostgreSQL instances on this machine.
    Returns list of dicts with keys: host, port, user, databases.
    Detects both TCP (127.0.0.1:port) and Unix socket connections.
    """
    results: List[Dict[str, str]] = []
    if not psql_path:
        return results

    # Users to try: current OS user first (peer auth: OS user = DB role),
    # then the conventional postgres/root accounts.
    users_to_try = ["postgres", "root"]
    try:
        import getpass
        cur = getpass.getuser()
        if cur and cur not in users_to_try:
            users_to_try.insert(0, cur)
    except Exception:
        pass

    # --- 1. Try Unix sockets first (common on Linux) ---
    # Scan every .s.PGSQL.* file so non-default ports (5433, 5434, ...)
    # are detected too, and keep going after the first hit so multiple
    # instances on different sockets are all reported.
    seen_ports: set = set()
    for sock in _find_socket_paths():
        port = _socket_port(sock)
        if port in seen_ports:
            continue  # same port already found (multi-dir sockets)
        host = os.path.dirname(sock)
        for user in users_to_try:
            out, _, rc = run_cmd(
                [psql_path, "-w", "-h", host, "-p", port, "-U", user,
                 "-d", "postgres", "-tAc", "SELECT current_database();"],
                env={"PGPASSWORD": ""}, timeout=3,
            )
            if rc == 0 and out.strip():
                db = out.strip()
                # List all databases on this server
                dbs_out, _, _ = run_cmd(
                    [psql_path, "-w", "-h", host, "-p", port, "-U", user,
                     "-d", "postgres", "-tAc",
                     "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"],
                    env={"PGPASSWORD": ""}, timeout=3,
                )
                databases = [d.strip() for d in dbs_out.strip().split("\n") if d.strip()] if dbs_out.strip() else [db]
                results.append({
                    "host": host,  # socket directory
                    "port": port,
                    "user": user,
                    "databases": ", ".join(databases),
                    "default_db": db,
                })
                seen_ports.add(port)
                break  # Found a working user on this socket

    # --- 2. Try TCP ports (fallback) — skip ports found via socket so an
    # instance that answered on its socket is not reported a second time.
    ports_to_try = ["5432", "5433", "5434", "5435", "5436"]

    for port in ports_to_try:
        if port in seen_ports:
            continue  # already found via Unix socket
        for user in users_to_try:
            # Try connecting with no password (common for local dev)
            out, _, rc = run_cmd(
                [psql_path, "-w", "-h", "127.0.0.1", "-p", port, "-U", user,
                 "-d", "postgres", "-tAc",
                 "SELECT current_database();"],
                env={"PGPASSWORD": ""},
                timeout=3,
            )
            if rc == 0 and out.strip():
                db = out.strip()
                # List all databases on this server
                dbs_out, _, _ = run_cmd(
                    [psql_path, "-w", "-h", "127.0.0.1", "-p", port, "-U", user,
                     "-d", "postgres", "-tAc",
                     "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"],
                    env={"PGPASSWORD": ""}, timeout=3,
                )
                databases = [d.strip() for d in dbs_out.strip().split("\n") if d.strip()] if dbs_out.strip() else [db]
                results.append({
                    "host": "127.0.0.1",
                    "port": port,
                    "user": user,
                    "databases": ", ".join(databases),
                    "default_db": db,
                })
                break  # Found this port, no need to try other users

    return results
