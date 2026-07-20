"use client";

import { useEffect, useState, useCallback } from "react";

// ─── Types ──────────────────────────────────────────────────

type TableRow = {
  table: string;
  local: number;
  supabase: number;
  ok: boolean;
};

type StatusData = {
  total_rows?: number;
  memories: number;
  local_size: string;
  remote_size: string;
  tables: TableRow[];
  synced: boolean;
  backup_count: number;
  last_backup: { file: string; size: number; date: number } | null;
  cron_active: boolean;
  error?: string;
};

type Toast = { msg: string; type: "ok" | "err" } | null;

// ─── Helpers ─────────────────────────────────────────────────

function fmt(s: number): string {
  if (s >= 1_000_000) return (s / 1_000_000).toFixed(1) + "M";
  if (s >= 1_000) return (s / 1_000).toFixed(1) + "K";
  return String(s);
}

function ago(ts: number): string {
  const d = Date.now() - ts * 1000;
  const h = Math.floor(d / 3600000);
  const m = Math.floor((d % 3600000) / 60000);
  if (h > 24) return `${Math.floor(h / 24)}h lalu`;
  if (h > 0) return `${h}j ${m}m lalu`;
  if (m > 0) return `${m}m lalu`;
  return "baru saja";
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000) return (bytes / 1_000_000).toFixed(1) + " MB";
  if (bytes >= 1_000) return (bytes / 1_000).toFixed(1) + " KB";
  return bytes + " B";
}

// ─── Theme Hook ─────────────────────────────────────────────

function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = localStorage.getItem("gaet-theme") as "dark" | "light" | null;
    if (saved) {
      setTheme(saved);
      document.documentElement.setAttribute("data-theme", saved);
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      setTheme(prefersDark ? "dark" : "light");
      document.documentElement.setAttribute("data-theme", prefersDark ? "dark" : "light");
    }
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("gaet-theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  return { theme, toggle };
}

// ─── Icons ──────────────────────────────────────────────────

function Icon({ children, size = 18 }: { children: React.ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

const Icons = {
  DB: () => <Icon><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></Icon>,
  Cloud: () => <Icon><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></Icon>,
  Sync: () => <Icon><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></Icon>,
  Upload: () => <Icon size={16}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></Icon>,
  Download: () => <Icon size={16}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></Icon>,
  Stop: () => <Icon size={16}><circle cx="12" cy="12" r="10"/><line x1="4" y1="4" x2="20" y2="20"/></Icon>,
  Check: () => <Icon size={14}><polyline points="20 6 9 17 4 12"/></Icon>,
  X: () => <Icon size={14}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></Icon>,
  Refresh: () => <Icon size={16}><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></Icon>,
  Activity: () => <Icon><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></Icon>,
  Archive: () => <Icon><rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></Icon>,
  Sun: () => <Icon size={18}><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></Icon>,
  Moon: () => <Icon size={18}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></Icon>,
  Clock: () => <Icon><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></Icon>,
  Server: () => <Icon><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></Icon>,
  Database: () => <Icon><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></Icon>,
};

// ─── Components ─────────────────────────────────────────────

function StatCard({
  icon,
  iconColor,
  label,
  value,
  subtitle,
  cardColor,
  children,
}: {
  icon: React.ReactNode;
  iconColor: string;
  label: string;
  value: string;
  subtitle?: string;
  cardColor: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={`stat-card ${cardColor}`}>
      <div className={`stat-icon ${iconColor}`}>{icon}</div>
      <div className="stat-content">
        <h3>{label}</h3>
        <div className="value">{value}</div>
        {subtitle && <div className="subtitle">{subtitle}</div>}
        {children}
      </div>
    </div>
  );
}

function SyncProgress({ synced, total }: { synced: number; total: number }) {
  const pct = total > 0 ? (synced / total) * 100 : 0;
  const color = pct === 100 ? "full" : pct > 0 ? "partial" : "none";

  return (
    <div className="sync-progress">
      <div className="progress-bar">
        <div className={`progress-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-text">
        {synced}/{total} tabel sinkron ({Math.round(pct)}%)
      </div>
    </div>
  );
}

// ─── Page ───────────────────────────────────────────────────

export default function Page() {
  const [data, setData] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast>(null);
  const { theme, toggle } = useTheme();

  const show = (msg: string, type: "ok" | "err") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch("/api/status");
      const d = await r.json();
      setData(d);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchStatus();
    const iv = setInterval(fetchStatus, 8000);
    return () => clearInterval(iv);
  }, [fetchStatus]);

  const act = async (action: string, label: string) => {
    setBusy(label);
    try {
      const r = await fetch(`/api/${action}`, { method: "POST" });
      const d = await r.json();
      if (d.ok) show(d.msg || "Selesai!", "ok");
      else show(d.msg || "Gagal", "err");
      fetchStatus();
    } catch { show("Gagal terhubung ke server", "err"); }
    finally { setBusy(null); }
  };

  if (loading) {
    return (
      <div className="app-container">
        <div className="loader">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  const d = data;
  const tables = d?.tables ?? [];
  const synced = d?.synced ?? false;
  const syncedCount = tables.filter((t) => t.ok).length;
  const totalCount = tables.length;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="logo">
            <img src="/gaet-logo.png" alt="gaet" className="logo-icon" style={{ width: 36, height: 36, borderRadius: 8, objectFit: "cover" }} />
            <div className="logo-text">
              <h1>gaet</h1>
              <p>Database Backup &amp; Sync</p>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button className="theme-toggle" onClick={toggle} title="Toggle theme">
              {theme === "dark" ? <Icons.Sun /> : <Icons.Moon />}
            </button>
            <button className="btn btn-secondary" onClick={fetchStatus} disabled={!!busy}>
              <Icons.Refresh /> Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="main-content">
        {/* Error banner */}
        {d?.error && (
          <div style={{
            background: "var(--red-bg)", border: "1px solid var(--red-subtle)",
            borderRadius: "var(--radius)", padding: "12px 16px", marginBottom: 20,
            fontSize: 14, color: "var(--red)", display: "flex", alignItems: "center", gap: 8
          }}>
            <Icons.X /> {d.error}
          </div>
        )}

        {/* Stat Cards */}
        <div className="stat-grid">
          <StatCard
            icon={<Icons.Database />}
            iconColor="accent"
            label="Tables"
            value={fmt(totalCount)}
            subtitle={d ? `${d.local_size ?? "?"} lokal` : "—"}
            cardColor="accent"
          />

          <StatCard
            icon={<Icons.Sync />}
            iconColor={synced ? "green" : "yellow"}
            label="Sync Status"
            value={synced ? "Synced" : "Not synced"}
            cardColor={synced ? "green" : "yellow"}
          >
            <SyncProgress synced={syncedCount} total={totalCount} />
          </StatCard>

          <StatCard
            icon={<Icons.Archive />}
            iconColor="purple"
            label="Backup"
            value={String(d?.backup_count ?? 0)}
            subtitle={d?.last_backup ? `Last ${ago(d.last_backup.date)}` : "No backup yet"}
            cardColor="purple"
          />

          <StatCard
            icon={<Icons.Activity />}
            iconColor={d?.cron_active ? "green" : "yellow"}
            label="Auto-Backup"
            value={d?.cron_active ? "Active" : "Inactive"}
            subtitle={d?.cron_active ? "Periodik" : "Jalankan manual"}
            cardColor={d?.cron_active ? "green" : "yellow"}
          />
        </div>

        {/* Actions */}
        <div className="section">
          <div className="section-header">
            <h2>
              <Icons.Server /> Actions
            </h2>
          </div>
          <div className="section-body">
            <div className="actions">
              <button className="btn btn-primary" onClick={() => act("push", "Push")} disabled={!!busy}>
                {busy === "Push" ? <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> : <Icons.Upload />}
                Push ke Cloud
              </button>
              <button className="btn btn-secondary" onClick={() => act("fetch", "Fetch")} disabled={!!busy}>
                {busy === "Fetch" ? <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> : <Icons.Download />}
                Fetch dari Cloud
              </button>
              {d?.cron_active ? (
                <button className="btn btn-danger" onClick={() => act("stop", "Stop")} disabled={!!busy}>
                  <Icons.Stop /> Stop Auto-Backup
                </button>
              ) : (
                <button className="btn btn-secondary" onClick={() => act("push?auto=1", "Auto")} disabled={!!busy}>
                  <Icons.Activity /> Enable Auto-Backup
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Tables Section */}
        <div className="section">
          <div className="section-header">
            <h2>
              <Icons.Database /> Database Tables
            </h2>
            <span className={`badge ${synced ? "badge-success" : "badge-warning"}`}>
              {synced ? <><Icons.Check /> Synced</> : <><Icons.X /> Not synced</>}
            </span>
          </div>
          <div className="section-body">
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Table</th>
                    <th style={{ textAlign: "right" }}>Local</th>
                    <th style={{ textAlign: "right" }}>Cloud</th>
                    <th style={{ textAlign: "center" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {tables.map((t) => (
                    <tr key={t.table}>
                      <td className="table-name">{t.table}</td>
                      <td className="table-num">{fmt(t.local)}</td>
                      <td className="table-num">{fmt(t.supabase)}</td>
                      <td style={{ textAlign: "center" }}>
                        {t.ok ? (
                          <span className="badge badge-success"><Icons.Check /> Sync</span>
                        ) : (
                          <span className="badge badge-danger"><Icons.X /> Diff</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {tables.length === 0 && (
                    <tr>
                      <td colSpan={4} style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
                        No table data
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer style={{ textAlign: "center", padding: "20px 0", fontSize: 13, color: "var(--text-muted)" }}>
          gaet v1.0.0 • Database Backup &amp; Sync
        </footer>
      </main>

      {/* Toast */}
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}
