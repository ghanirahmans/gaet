import { NextResponse } from "next/server";
import { execSync } from "child_process";

export async function GET() {
  try {
    const out = execSync("gaet status --json 2>/dev/null", { timeout: 30000, encoding: "utf-8" });
    const data = JSON.parse(out);
    return NextResponse.json(data);
  } catch {
    // Fallback: try Python module directly
    try {
      const out2 = execSync(
        `python3 -c "
import sys, json, os
sys.path.insert(0, os.path.expanduser('~/.gaet'))
sys.path.insert(0, os.path.expanduser('~/Projects/gaet/scripts'))
from status import get_status
print(json.dumps(get_status()))
" 2>/dev/null`, { timeout: 30000, encoding: "utf-8" }
      );
      return NextResponse.json(JSON.parse(out2));
    } catch {
      return NextResponse.json({
        memories: 0, synced: false, local_size: "?", remote_size: "?",
        tables: [], backup_count: 0, last_backup: null, cron_active: false,
        error: "Tidak bisa dapat status"
      });
    }
  }
}
