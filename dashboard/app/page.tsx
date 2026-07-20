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

function sizeLabel(s: number): string {
  if (s >= 1_000_000) return (s / 1_000_000).toFixed(1) + " MB";
  if (s >= 1_000) return (s / 1_000).toFixed(1) + " KB";
  return s + " B";
}

function ago(ts: number): string {
  const d = Date.now() - ts * 1000;
  const h = Math.floor(d / 3600000);
  const m = Math.floor((d % 3600000) / 60000);
  if (h > 0) return `${h}h ${m}m lalu`;
  if (m > 0) return `${m}m lalu`;
  return "baru saja";
}

// ─── Icons (inline SVG) ─────────────────────────────────────

function IconDB() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>;
}
function IconCloud() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>;
}
function IconSync() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>;
}
function IconUpload() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>;
}
function IconDownload() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>;
}
function IconStop() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4" y1="4" x2="20" y2="20"/></svg>;
}
function IconCheck() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>;
}
function IconX() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>;
}
function IconRefresh() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>;
}
function IconActivity() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>;
}
function IconArchive() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></svg>;
}

// ─── Page ───────────────────────────────────────────────────

export default function Page() {
  const [data, setData] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast>(null);

  const show = (msg: string, type: "ok" | "err") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch("/api/status");
      const d = await r.json();
      setData(d);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
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
    } catch {
      show("Gagal terhubung ke server", "err");
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <div className="spin" style={{ width: 32, height: 32, border: "3px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%" }} />
      </div>
    );
  }

  const d = data;
  const error = d?.error;
  const tables = d?.tables ?? [];
  const synced = d?.synced ?? false;

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "32px 20px" }}>
      {/* Header */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, letterSpacing: "-0.03em" }}>
            gaet <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>dashboard</span>
          </h1>
          <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--text-secondary)" }}>
            Database Backup &amp; Sync
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-secondary" onClick={fetchStatus} disabled={!!busy}>
            <IconRefresh /><span>Refresh</span>
          </button>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div style={{ background: "var(--red-bg)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "var(--radius)", padding: "12px 16px", marginBottom: 20, fontSize: 14, color: "var(--red)" }}>
          <IconX /> {error}
        </div>
      )}

      {/* Stat cards */}
      <div className="dashboard-grid" style={{ marginBottom: 20 }}>
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ color: "var(--accent)" }}><IconDB /></span>
            <span className="stat-label">Memori</span>
          </div>
          <div className="stat-value">{d ? fmt(d.memories) : "?"}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
            {d?.local_size ?? "?"} lokal
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ color: synced ? "var(--green)" : "var(--yellow)" }}><IconSync /></span>
            <span className="stat-label">Sinkronisasi</span>
          </div>
          <div className="stat-value" style={{ color: synced ? "var(--green)" : "var(--yellow)" }}>
            {synced ? "Tersinkron" : "Tidak sinkron"}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
            {d?.remote_size ?? "?"} cloud
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ color: "var(--green)" }}><IconArchive /></span>
            <span className="stat-label">Backup</span>
          </div>
          <div className="stat-value">{d?.backup_count ?? 0}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
            {d?.last_backup ? `Terakhir ${ago(d.last_backup.date)}` : "Belum ada backup"}
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ color: d?.cron_active ? "var(--green)" : "var(--text-muted)" }}><IconActivity /></span>
            <span className="stat-label">Auto-Backup</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
            <span className={`pulse-dot ${d?.cron_active ? "active" : "inactive"}`} />
            <span style={{ fontSize: 14, fontWeight: 600 }}>{d?.cron_active ? "Aktif" : "Tidak aktif"}</span>
          </div>
        </div>
      </div>

      {/* Tables */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 12px" }}>Tabel Database</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tabel</th>
                <th style={{ textAlign: "right" }}>Lokal</th>
                <th style={{ textAlign: "right" }}>Cloud</th>
                <th style={{ textAlign: "center" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {tables.map((t) => (
                <tr key={t.table}>
                  <td style={{ fontWeight: 500 }}>{t.table}</td>
                  <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmt(t.local)}</td>
                  <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmt(t.supabase)}</td>
                  <td style={{ textAlign: "center" }}>
                    {t.ok ? (
                      <span className="badge-ok"><IconCheck /> Sinkron</span>
                    ) : (
                      <span className="badge-fail"><IconX /> Beda</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button className="btn btn-primary" onClick={() => act("push", "Push")} disabled={!!busy}>
          {busy === "Push" ? <span className="spin" style={{ display: "inline-block", width: 16, height: 16, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "white", borderRadius: "50%" }} /> : <IconUpload />}
          <span>Push ke Cloud</span>
        </button>
        <button className="btn btn-secondary" onClick={() => act("fetch", "Fetch")} disabled={!!busy}>
          {busy === "Fetch" ? <span className="spin" /> : <IconDownload />}
          <span>Fetch dari Cloud</span>
        </button>
        {d?.cron_active ? (
          <button className="btn btn-danger" onClick={() => act("stop", "Stop")} disabled={!!busy}>
            <IconStop /> <span>Stop Auto-Backup</span>
          </button>
        ) : (
          <button className="btn btn-secondary" onClick={() => act("push?auto=1", "Auto")} disabled={!!busy}>
            <IconActivity /> <span>Aktifkan Auto-Backup</span>
          </button>
        )}
      </div>

      {/* Toast */}
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}
