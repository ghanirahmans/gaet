# @ghanirahmans/gaet (Official TypeScript / JavaScript SDK)

> Official TypeScript & JavaScript client SDK for **Gaet** — Zero-dependency PostgreSQL Database Backup & Cloud Sync CLI & Service.

[![npm version](https://img.shields.io/npm/v/@ghanirahmans/gaet.svg)](https://www.npmjs.com/package/@ghanirahmans/gaet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Architecture Overview

```text
 ┌───────────────────────────┐      HTTP REST API       ┌───────────────────────────┐
 │   Your Web Application    │   (http://127.0.0.1:6161) │     Gaet Service Daemon   │
 │   (Next.js / React / Node)├─────────────────────────►│     (gaet serve --auto)   │
 └─────────────┬─────────────┘                          └─────────────┬─────────────┘
               │                                                      │
               │ import { gaet } from '@ghanirahmans/gaet'             │ PostgreSQL Engine
               ▼                                                      ▼
   ┌──────────────────────┐                             ┌───────────────────────────┐
   │  TypeScript SDK      │                             │ Local DB ◄──► Cloud Remote│
   └──────────────────────┘                             └───────────────────────────┘
```

---

## ⚡ Installation

```bash
npm install @ghanirahmans/gaet
# or
pnpm add @ghanirahmans/gaet
# or
yarn add @ghanirahmans/gaet
# or
bun add @ghanirahmans/gaet
```

---

## ⚙️ Prerequisites

Ensure the `gaet` CLI service daemon is running in your environment:

```bash
# Start background dashboard & REST API server (port 6161)
gaet serve

# Or register as auto-starting OS daemon (systemd / launchd / Task Scheduler)
gaet serve --auto
```

---

## 🚀 Quick Start (Next.js / TypeScript)

```typescript
import { gaet } from '@ghanirahmans/gaet';

// 1. Check Database Sync Status
const status = await gaet.status();
console.log('Local DB connected:', status.local_ok);
console.log('Cloud Remote configured:', status.remote_configured);

// 2. Trigger Cloud Backup (Push)
const pushResult = await gaet.push();
if (pushResult.ok) {
  console.log('Backup successful! Snapshot:', pushResult.snapshot);
}

// 3. List Local Snapshots
const { snapshots } = await gaet.snapshots();
snapshots.forEach(s => {
  console.log(`${s.name} (${s.size_mb} MB) - ${s.mod_time}`);
});
```

---

## 💻 Integration Examples

### 1. Next.js App Router API Route (`app/api/backup/route.ts`)

```typescript
import { NextResponse } from 'next/server';
import { gaet } from '@ghanirahmans/gaet';

export async function POST() {
  try {
    const result = await gaet.push();
    if (!result.ok) {
      return NextResponse.json({ error: result.msg }, { status: 500 });
    }
    return NextResponse.json({ success: true, snapshot: result.snapshot });
  } catch (error: any) {
    return NextResponse.json({ error: 'Gaet daemon offline: ' + error.message }, { status: 503 });
  }
}
```

### 2. React Admin Dashboard Button

```tsx
import React, { useState } from 'react';
import { gaet } from '@ghanirahmans/gaet';

export function BackupButton() {
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');

  const handleBackup = async () => {
    setLoading(true);
    try {
      const res = await gaet.push();
      setStatusMsg(res.ok ? `Backup created: ${res.snapshot}` : `Error: ${res.msg}`);
    } catch (err: any) {
      setStatusMsg('Daemon offline or unreachable');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={handleBackup} disabled={loading}>
        {loading ? 'Creating Backup...' : 'Push Database Backup'}
      </button>
      {statusMsg && <p>{statusMsg}</p>}
    </div>
  );
}
```

---

## 🛠️ Custom Client Configuration

```typescript
import { GaetClient } from '@ghanirahmans/gaet';

const gaetClient = new GaetClient({
  baseUrl: 'http://127.0.0.1:6161', // Custom REST API endpoint
  timeout: 120000,                  // 120 seconds timeout for large database backups
});

const checkResult = await gaetClient.check();
console.log('PostgreSQL tools ok:', checkResult.checks.tools.ok);
```

---

## 📚 API Reference

| Method | Return Type | Description |
| :--- | :--- | :--- |
| `gaet.status()` | `Promise<GaetStatusResponse>` | Returns local & cloud DB connectivity, host, and user details. |
| `gaet.push()` | `Promise<GaetPushResponse>` | Triggers a real-time database dump and sync to Cloud Remote. |
| `gaet.fetch()` | `Promise<GaetFetchResponse>` | Fetches cloud database state and restores into local database. |
| `gaet.restore(name?)` | `Promise<GaetRestoreResponse>` | Restores local DB from a specific `.dump` snapshot file. |
| `gaet.snapshots()` | `Promise<GaetSnapshotsResponse>` | Lists all local `.dump` snapshot files in `~/.gaet/backups`. |
| `gaet.deleteSnapshot(name)` | `Promise<GaetGenericResponse>` | Deletes a specific snapshot file from disk. |
| `gaet.logs()` | `Promise<GaetLogsResponse>` | Retrieves structured audit log records (`~/.gaet/gaet.log`). |
| `gaet.check()` | `Promise<GaetCheckResponse>` | Executes preflight diagnostics (`pg_dump`, `psql`, auth checks). |
| `gaet.diff()` | `Promise<GaetDiffResponse>` | Compares table count schema alignment between Local DB and Cloud DB. |

---

## 🏷️ Type Definitions Import

```typescript
import type {
  GaetStatusResponse,
  GaetPushResponse,
  GaetFetchResponse,
  GaetSnapshotsResponse,
  GaetSnapshotInfo,
  GaetCheckResponse,
  GaetLogsResponse,
  GaetLogEntry,
} from '@ghanirahmans/gaet';
```

---

## 📄 License

MIT © [Ghani Rahman](https://github.com/ghanirahmans)

