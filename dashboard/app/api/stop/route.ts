import { NextResponse } from "next/server";
import { execSync } from "child_process";

export async function POST() {
  try {
    execSync("gaet stop", { timeout: 10000, encoding: "utf-8" });
    return NextResponse.json({ ok: true, msg: "Auto-backup dihentikan" });
  } catch (e: any) {
    return NextResponse.json({ ok: false, msg: `Gagal stop: ${e.message?.slice(0, 100) || "error"}` });
  }
}
