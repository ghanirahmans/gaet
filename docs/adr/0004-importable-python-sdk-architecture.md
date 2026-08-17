# ADR-0004: Dual-Personality Architecture (CLI Tool & Importable Python SDK)

## Status
Accepted (Future Architectural Goal & Design Constraint)

## Context
Currently, Gaet is primarily invoked as a standalone CLI tool via terminal commands (`gaet push`, `gaet restore`, etc.). However, modern developers, system administrators, and backend engineers often want to embed PostgreSQL backup and restore capabilities directly into their own Python applications, web services (FastAPI, Django, Flask), or custom automation scripts without spawning external shell processes.

## Decision
We decided to design all future Gaet modules around a **Dual-Personality Architecture**:
Gaet must function seamlessly both as a **standalone CLI tool** and as a **clean, importable Python Library SDK**.

### Programmatic SDK Specification

1. **Python Package Export (`import gaet`)**:
   - `src/gaet/__init__.py` exposes high-level programmatic interfaces (e.g., `GaetEngine`, `backup()`, `restore()`, `get_status()`, `list_snapshots()`).
   
2. **Programmatic API Design**:
   ```python
   import gaet

   # Initialize client programmatically
   client = gaet.Client(local_url="postgresql://postgres@localhost:5432/mydb", remote_url="postgresql://user:pass@cloud.supabase.com:5432/db")

   # Execute backup programmatically returning structured objects
   result = client.push()
   print(f"Snapshot created: {result.filename} ({result.size_bytes} bytes)")

   # Programmatic restore
   client.restore(snapshot="gaet_20260817_120000.dump", yes=True)
   ```

3. **No Direct `sys.exit()` in Business Functions**:
   - Business logic functions in `src/gaet/` must raise typed Python exceptions (e.g. `GaetConfigError`, `GaetBackupError`, `GaetConnectionError`) rather than calling `sys.exit()` directly.
   - `cli.py` handles exceptions and maps them to clean exit codes and ASCII status messages.

## Consequences
- **Positive**: Enables developers to integrate Gaet directly as a PyPI package (`pip install gaet`) or Python module in third-party codebases.
- **Positive**: Clear separation of programmatic business logic from CLI presentation logic.
- **Negative**: Requires strict exception handling instead of calling `sys.exit()` or `die()` inside core helper functions.
