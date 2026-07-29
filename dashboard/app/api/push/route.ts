import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export async function POST(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const auto = searchParams.get("auto");
    const cmd = auto ? `gaet push --auto=${auto}` : "gaet push";
    await execAsync(cmd, { timeout: 180000, encoding: "utf-8" });
    return NextResponse.json({ ok: true, msg: "Push ke cloud selesai!" });
  } catch (e: any) {
    return NextResponse.json({ ok: false, msg: `Push gagal: ${e.message?.slice(0, 100) || "error"}` });
  }
}

