import { NextRequest, NextResponse } from "next/server";
import { execFileSync } from "child_process";
import { findGaet } from "../utils";

export async function POST(req: NextRequest) {
  try {
    const origin = req.headers.get("origin");
    const allowedOrigin = process.env.DASHBOARD_ORIGIN || "http://localhost:9191";
    if (origin && origin !== allowedOrigin) {
      return NextResponse.json({ ok: false, msg: "Forbidden" }, { status: 403 });
    }

    const gaet = findGaet();
    execFileSync(gaet, ["fetch"], { timeout: 180000, encoding: "utf-8" });
    return NextResponse.json({ ok: true, msg: "Fetch dari cloud selesai!" });
  } catch {
    return NextResponse.json({ ok: false, msg: "Fetch gagal" });
  }
}
