import type {
  GaetCheckResponse,
  GaetClientOptions,
  GaetDetectResponse,
  GaetDiffResponse,
  GaetDoctorResponse,
  GaetExportResponse,
  GaetFetchResponse,
  GaetLogsResponse,
  GaetPushResponse,
  GaetRemoteTestResponse,
  GaetSnapshotsResponse,
  GaetStartServerOptions,
  GaetStatusResponse,
} from './types.js';

/**
 * Official Gaet SDK Client for Node.js, Next.js, React, Bun, and Deno.
 *
 * Communicates with the background `gaet serve` REST API daemon.
 */
export class GaetClient {
  private baseUrl: string;
  private timeout: number;
  private fetchFn: typeof globalThis.fetch;
  private spawnedProcess: any = null;

  constructor(options: GaetClientOptions = {}) {
    this.baseUrl = (options.baseUrl || 'http://127.0.0.1:6161').replace(/\/+$/, '');
    this.timeout = options.timeout ?? 60000;
    this.fetchFn = options.fetch || globalThis.fetch;

    if (!this.fetchFn) {
      throw new Error('Global fetch API is not available. Please pass a custom fetch implementation in GaetClientOptions.');
    }
  }

  /**
   * Helper method to perform typed HTTP requests to Gaet REST API.
   */
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await this.fetchFn(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          ...(options.headers || {}),
        },
      });

      if (!response.ok) {
        let errMessage = `HTTP ${response.status} ${response.statusText}`;
        try {
          const body = await response.json();
          if (body && (body.error || body.msg)) {
            errMessage = body.error || body.msg;
          }
        } catch {
          // ignore json parse error on non-ok status
        }
        throw new Error(`Gaet API Error (${path}): ${errMessage}`);
      }

      return (await response.json()) as T;
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error(`Gaet API Request Timeout (${path}) after ${this.timeout}ms`);
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Auto-start the gaet serve daemon process directly from Node.js / backend code.
   *
   * If gaet serve is already running, this method returns immediately without spawning a duplicate process.
   */
  async startServer(options: GaetStartServerOptions = {}): Promise<{ ok: boolean; msg: string; pid?: number }> {
    // 1. Check if server is already running
    try {
      await this.status();
      return { ok: true, msg: 'Gaet service daemon is already running.' };
    } catch {
      // Server is not running, proceed to spawn
    }

    const binPath = options.binPath || 'gaet';
    const port = options.port || 6161;

    try {
      const childProcess = await import('node:child_process');
      const processEnv = typeof process !== 'undefined' ? process.env : {};
      const spawnEnv = {
        ...processEnv,
        ...(options.env || {}),
      };

      this.spawnedProcess = childProcess.spawn(binPath, ['serve', '--no-open', '--port', String(port)], {
        detached: false,
        stdio: 'ignore',
        env: spawnEnv as Record<string, string>,
      });

      // Poll until server responds or 10s timeout
      const startTime = Date.now();
      while (Date.now() - startTime < 10000) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        try {
          await this.status();
          return { ok: true, msg: 'Gaet serve daemon started successfully.', pid: this.spawnedProcess.pid };
        } catch {
          // continue polling
        }
      }

      throw new Error(`Failed to verify Gaet serve daemon startup on port ${port} after 10s.`);
    } catch (err: any) {
      throw new Error(`Unable to start Gaet serve process: ${err.message}`);
    }
  }

  /**
   * Stop the gaet serve daemon process spawned by startServer().
   */
  async stopServer(): Promise<{ ok: boolean; msg: string }> {
    if (this.spawnedProcess) {
      try {
        this.spawnedProcess.kill('SIGTERM');
        this.spawnedProcess = null;
        return { ok: true, msg: 'Gaet serve daemon stopped.' };
      } catch (err: any) {
        return { ok: false, msg: `Failed to stop process: ${err.message}` };
      }
    }
    return { ok: true, msg: 'No active spawned Gaet process to stop.' };
  }

  /**
   * Check connection status of local and cloud database.
   * Corresponds to `gaet status`.
   */
  async status(): Promise<GaetStatusResponse> {
    return this.request<GaetStatusResponse>('/api/status');
  }

  /**
   * Trigger a real-time database backup from local PostgreSQL to Cloud Remote DB.
   * Corresponds to `gaet push`.
   */
  async push(): Promise<GaetPushResponse> {
    return this.request<GaetPushResponse>('/api/push', { method: 'POST' });
  }

  /**
   * Fetch the latest snapshot from Cloud Remote DB and restore it locally.
   * Corresponds to `gaet fetch`.
   */
  async fetch(): Promise<GaetFetchResponse> {
    return this.request<GaetFetchResponse>('/api/fetch', { method: 'POST' });
  }

  /**
   * Restore a specific snapshot or latest snapshot to local DB.
   * Corresponds to `gaet restore`.
   */
  async restore(snapshotName?: string): Promise<GaetFetchResponse> {
    return this.request<GaetFetchResponse>('/api/restore', {
      method: 'POST',
      body: JSON.stringify({ snapshot: snapshotName }),
    });
  }

  /**
   * Get list of local .dump backup snapshots.
   * Corresponds to `gaet snapshots`.
   */
  async snapshots(): Promise<GaetSnapshotsResponse> {
    return this.request<GaetSnapshotsResponse>('/api/snapshots');
  }

  /**
   * Delete a specific local snapshot file.
   */
  async deleteSnapshot(snapshotName: string): Promise<{ ok: boolean; msg: string }> {
    return this.request<{ ok: boolean; msg: string }>('/api/snapshots/delete', {
      method: 'DELETE',
      body: JSON.stringify({ name: snapshotName }),
    });
  }

  /**
   * Get structured audit log records.
   * Corresponds to `gaet log`.
   */
  async logs(): Promise<GaetLogsResponse> {
    return this.request<GaetLogsResponse>('/api/logs');
  }

  /**
   * Execute preflight diagnostic checks.
   * Corresponds to `gaet check`.
   */
  async check(): Promise<GaetCheckResponse> {
    return this.request<GaetCheckResponse>('/api/check');
  }

  /**
   * Compare table count schema diff between Local DB and Cloud DB.
   * Corresponds to `gaet diff`.
   */
  async diff(): Promise<GaetDiffResponse> {
    return this.request<GaetDiffResponse>('/api/diff');
  }

  /**
   * Execute full system doctor diagnostics.
   * Corresponds to `gaet doctor`.
   */
  async doctor(): Promise<GaetDoctorResponse> {
    return this.request<GaetDoctorResponse>('/api/doctor');
  }

  /**
   * Auto-scan for active local PostgreSQL socket and TCP instances.
   * Corresponds to `gaet detect`.
   */
  async detect(): Promise<GaetDetectResponse> {
    return this.request<GaetDetectResponse>('/api/detect');
  }

  /**
   * Test connectivity to the Cloud Remote database URL.
   * Corresponds to `gaet remote test`.
   */
  async testRemote(): Promise<GaetRemoteTestResponse> {
    return this.request<GaetRemoteTestResponse>('/api/remote/test');
  }

  /**
   * Export configuration as shell export statements.
   * Corresponds to `gaet export`.
   */
  async export(): Promise<GaetExportResponse> {
    return this.request<GaetExportResponse>('/api/export');
  }

  /**
   * Read current environment configuration variables from ~/.gaet/.env.
   */
  async getConfig(): Promise<Record<string, string>> {
    return this.request<Record<string, string>>('/api/config');
  }

  /**
   * Update configuration variables in ~/.gaet/.env.
   */
  async setConfig(config: Record<string, string>): Promise<{ ok: boolean; msg: string }> {
    return this.request<{ ok: boolean; msg: string }>('/api/config', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }
}
