import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export async function POST() {
  try {
    await execAsync("gaet fetch", { timeout: 180000, encoding: "utf-8" });
    return NextResponse.json({ ok: true, msg: "Fetch dari cloud selesai!" });
  } catch (e: any) {
    return NextResponse.json({ ok: false, msg: `Fetch gagal: ${e.message?.slice(0, 100) || "error"}` });
  }
}

