import { execFileSync } from "child_process";
import { existsSync } from "fs";

let _gaetPath: string | null = null;

function findInPath(name: string): string | null {
  const pathDirs = (process.env.PATH || "").split(":");
  for (const dir of pathDirs) {
    const full = `${dir}/${name}`;
    if (existsSync(full)) return full;
  }
  return null;
}

export function findGaet(): string {
  if (_gaetPath) return _gaetPath;

  const envPath = process.env.GAET_PATH;
  if (envPath && existsSync(envPath)) {
    _gaetPath = envPath;
    return _gaetPath;
  }

  const found = findInPath("gaet") || findInPath("gaet.py");
  if (found) {
    _gaetPath = found;
    return _gaetPath;
  }

  _gaetPath = "gaet";
  return _gaetPath;
}
