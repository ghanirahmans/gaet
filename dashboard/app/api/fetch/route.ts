import { NextResponse } from "next/server";
import { execSync } from "child_process";

export async function POST() {
  try {
    execSync("gaet fetch", { timeout: 180000, encoding: "utf-8" });
    return NextResponse.json({ ok: true, msg: "Fetch dari cloud selesai!" });
  } catch (e: any) {
    return NextResponse.json({ ok: false, msg: `Fetch gagal: ${e.message?.slice(0, 100) || "error"}` });
  }
}
