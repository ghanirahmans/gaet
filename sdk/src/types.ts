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
 * Status check response from `GET /api/status`.
 */
export interface GaetStatusResponse {
  local_ok: boolean;
  host: string;
  port: string;
  user: string;
  db: string;
  remote_configured: boolean;
  remote_host: string;
}

/**
 * Backup / push response from `POST /api/push`.
 */
export interface GaetPushResponse {
  ok: boolean;
  msg: string;
  snapshot?: string;
  error?: string;
}

/**
 * Cloud restore response from `POST /api/fetch`.
 */
export interface GaetFetchResponse {
  ok: boolean;
  msg: string;
  error?: string;
}

/**
 * Local snapshot item details.
 */
export interface GaetSnapshotItem {
  name: string;
  size_mb: number;
  mod_time: string;
}

/**
 * Snapshots list response from `GET /api/snapshots`.
 */
export interface GaetSnapshotsResponse {
  count: number;
  snapshots: GaetSnapshotItem[];
}

/**
 * Audit log record.
 */
export interface GaetLogEntry {
  timestamp: string;
  command: string;
  status: string;
  snapshot?: string;
  details?: string;
}

/**
 * Logs response from `GET /api/logs`.
 */
export interface GaetLogsResponse {
  count: number;
  logs: GaetLogEntry[];
}

/**
 * Check diagnostics response from `GET /api/check`.
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
    remote_db: {
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
 */
export interface GaetDiffResponse {
  command: string;
  local_db: {
    ok: boolean;
    table_count: number;
  };
  cloud_db: {
    ok: boolean;
    table_count: number;
  };
}
