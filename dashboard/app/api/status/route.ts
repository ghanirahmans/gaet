import { NextRequest, NextResponse } from "next/server";
import { execFileSync } from "child_process";
import { findGaet } from "../utils";

export async function GET(req: NextRequest) {
  try {
    const origin = req.headers.get("origin");
    const allowedOrigin = process.env.DASHBOARD_ORIGIN || "http://localhost:9191";
    if (origin && origin !== allowedOrigin) {
      return NextResponse.json({ ok: false, msg: "Forbidden" }, { status: 403 });
    }

    const gaet = findGaet();
    const out = execFileSync(gaet, ["status", "--json"], { timeout: 30000, encoding: "utf-8" });
    const data = JSON.parse(out);
    return NextResponse.json({
      total_rows: data.total_rows,
      synced: data.synced,
      local_size: data.local_size,
      remote_size: data.remote_size,
      tables: data.tables,
      backup_count: data.backup_count,
      last_backup: data.last_backup,
      cron_active: data.cron_active,
    });
  } catch {
    return NextResponse.json({
      total_rows: 0, synced: false, local_size: "?", remote_size: "?",
      tables: [], backup_count: 0, last_backup: null, cron_active: false,
      error: "Tidak bisa dapat status"
    });
  }
}
