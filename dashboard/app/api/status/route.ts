import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export async function GET() {
  try {
    const { stdout } = await execAsync("gaet status --json", { timeout: 30000, encoding: "utf-8" });
    const data = JSON.parse(stdout.trim());
    return NextResponse.json(data);
  } catch {
    // Fallback: try Python module directly
    const pythonExe = process.platform === "win32" ? "python" : "python3";
    try {
      const { stdout: out2 } = await execAsync(
        `${pythonExe} -c "
import sys, json, os
sys.path.insert(0, os.path.expanduser('~/.gaet'))
sys.path.insert(0, os.path.expanduser('~/Projects/gaet/scripts'))
from status import get_status
print(json.dumps(get_status()))
"`, { timeout: 30000, encoding: "utf-8" }
      );
      return NextResponse.json(JSON.parse(out2.trim()));
    } catch {
      return NextResponse.json({
        memories: 0, synced: false, local_size: "?", remote_size: "?",
        tables: [], backup_count: 0, last_backup: null, cron_active: false,
        error: "Tidak bisa dapat status"
      });
    }
  }
}

