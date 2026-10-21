/**
 * Type definitions for the @ghanirahmans/gaet SDK.
 *
 * These interfaces are derived from the REST API response shapes emitted by
 * `pkg/serve/server.go` (`sendJSON(w, map[string]any{...})`). When the API
 * changes, update this file to match. Each interface carries an inline
 * reference comment to the handler that produces it.
 */

/**
 * Options for configuring the GaetClient SDK instance.
 */
export interface GaetClientOptions {
  /**
   * Base URL of the running Gaet REST API service (`gaet serve`).
   * @default "http://127.0.0.1:6161"
   */
  baseUrl?: string;

  /**
   * Request timeout in milliseconds.
   * @default 60000 (60 seconds)
   */
  timeout?: number;

  /**
   * Optional custom fetch implementation (useful for SSR/edge runtimes).
   */
  fetch?: typeof globalThis.fetch;
}

/**
 * Options for auto-starting the Gaet serve daemon via `startServer()`.
 */
export interface GaetStartServerOptions {
  /**
   * Custom path to the gaet CLI binary executable.
   * @default "gaet" (searched in system PATH)
   */
  binPath?: string;

  /**
   * Port for the gaet serve daemon to listen on.
   * @default 6161
   */
  port?: number;

  /**
   * Environment variables to pass directly to the gaet process (e.g. GAET_REMOTE_URL, GAET_LOCAL_DB_NAME).
   * Automatically inherits process.env by default.
   */
  env?: Record<string, string>;
}

/**
 * Row-level table sync status item.
 * Produced by: handleStatus → "tables" field.
 */
export interface GaetTableItem {
  table: string;
  local: number;     // -1 when missing
  supabase: number;  // -1 when missing
  ok: boolean;
}

/**
 * Status check response from `GET /api/status`.
 * Matches: handleStatus sendJSON(...) in pkg/serve/server.go.
 */
export interface GaetStatusResponse {
  local_ok: boolean;
  host: string;
  port: string;
  user: string;
  db: string;
  has_pass: boolean;
  remote_configured: boolean;
  remote_host: string;
  env_file: string;
  cron_active: boolean;
  cron_hours: number;
  scheduler_name: string;
  tables: GaetTableItem[];
}

/**
 * Backup / push response from `POST /api/push`.
 * Matches: handlePush sendJSON(...) in pkg/serve/server.go.
 */
export interface GaetPushResponse {
  ok: boolean;
  msg: string;
  snapshot?: string;
  error?: string;
}

/**
 * Cloud restore response from `POST /api/fetch`.
 * Matches: handleFetch sendJSON(...) in pkg/serve/server.go.
 */
export interface GaetFetchResponse {
  ok: boolean;
  msg: string;
  error?: string;
}

/**
 * Local snapshot item details.
 * Matches: handleSnapshots "snapshots" item struct in pkg/serve/server.go.
 */
export interface GaetSnapshotItem {
  name: string;
  filename: string;
  size_mb: number;
  mod_time: string;
  created_at: string;
  full_path: string;
}

/**
 * Snapshots list response from `GET /api/snapshots`.
 * Matches: handleSnapshots sendJSON(...) in pkg/serve/server.go.
 */
export interface GaetSnapshotsResponse {
  count: number;
  snapshots: GaetSnapshotItem[];
  backup_dir: string;
}

/**
 * Audit log record representing a single JSON line in ~/.gaet/backups/gaet.log.
 * Note: the /api/logs endpoint returns raw log lines as plain strings, not
 * this structured shape. This interface documents the on-disk JSON log format.
 */
export interface GaetLogEntry {
  timestamp: string;
  level: string;            // INFO, WARN, ERROR
  category: string;         // BACKUP, CONFIG, REMOTE, SCHEDULER, SNAPSHOT
  action: string;           // PUSH, FETCH, RESTORE, INIT, REMOTE_SET, SCHEDULE_ENABLE
  status: string;           // SUCCESS, FAILED
  message?: string;
  details?: Record<string, unknown>;
}

/**
 * Logs response from `GET /api/logs`.
 * Matches: handleLogs sendJSON(...) — returns {"logs": string[]}.
 */
export interface GaetLogsResponse {
  logs: string[];
}

/**
 * Check diagnostics response from `GET /api/check`.
 * Matches: handleCheck sendJSON(...) in pkg/serve/server.go.
 * Note: the CLI `gaet check --json` (pkg/status/status.go) additionally
 * includes a `remote_db` object in `checks`; that field is optional here.
 */
export interface GaetCheckResponse {
  ok: boolean;
  checks: {
    tools: {
      ok: boolean;
      pg_dump: string;
      pg_restore: string;
      psql: string;
    };
    local_db: {
      ok: boolean;
      host: string;
      port: string;
      user: string;
      database: string;
    };
    remote_db?: {
      configured: boolean;
      reachable: boolean;
      host?: string;
      port?: string;
      db?: string;
    };
    backup_dir: {
      ok: boolean;
      count: number;
    };
  };
}

/**
 * Schema difference response from `GET /api/diff`.
 * Matches: handleDiff sendJSON(...) in pkg/serve/server.go, which emits only
 * {"ok", "output"}. The richer command/local_db/cloud_db shape is emitted by the
 * CLI's `gaet diff --json` (pkg/status/status.go) — a different code path the SDK
 * does not call, so it is not modeled here.
 */
export interface GaetDiffResponse {
  ok: boolean;
  output: string;
}

/**
 * Doctor diagnostic response from `GET /api/doctor`.
 * Matches: handleDoctor sendJSON(...) in pkg/serve/server.go.
 */
export interface GaetDoctorResponse {
  ok: boolean;
  issues: number;
  output: string;
}

/**
 * Local PostgreSQL scanner response from `GET /api/detect`.
 * Matches: handleDetect sendJSON(...) / detect.DBInstance in pkg/serve/server.go.
 */
export interface GaetDetectResponse {
  ok: boolean;
  instances: Array<{
    host: string;
    port: string;
    user: string;
    databases: string[];
    default_db: string;
    is_socket: boolean;
  }>;
}

/**
 * Cloud remote test connection response from `POST /api/remote/test`.
 * Matches: handleRemoteTest sendJSON(...) in pkg/serve/server.go.
 */
export interface GaetRemoteTestResponse {
  ok: boolean;
  connected: boolean;
  msg: string;
  /**
   * Absent on the invalid/empty-URL early-return branch of handleRemoteTest
   * (pkg/serve/server.go), which sends only {ok, connected, msg}.
   */
  output?: string;
}

/**
 * Environment export response from `GET /api/export`.
 * Matches: handleExport sendJSON(...) in pkg/serve/server.go.
 */
export interface GaetExportResponse {
  ok: boolean;
  env_vars: string;
}

/**
 * Configuration response from `GET /api/config`.
 * Matches: handleConfig GET sendJSON(...) in pkg/serve/server.go.
 */
export interface GaetConfigResponse {
  config: Record<string, string>;
  masked_config: Record<string, string>;
  env_file: string;
}
