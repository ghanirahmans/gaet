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

    const { searchParams } = new URL(req.url);
    const auto = searchParams.get("auto");
    if (auto !== null && !/^\d+$/.test(auto)) {
      return NextResponse.json({ ok: false, msg: "Parameter auto tidak valid" }, { status: 400 });
    }
    const gaet = findGaet();
    const args = auto ? ["push", `--auto=${auto}`] : ["push"];
    execFileSync(gaet, args, { timeout: 180000, encoding: "utf-8" });
    return NextResponse.json({ ok: true, msg: "Push ke cloud selesai!" });
  } catch {
    return NextResponse.json({ ok: false, msg: "Push gagal" });
  }
}
