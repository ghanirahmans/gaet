# @ghanirahmans/gaet

Official TypeScript and JavaScript client SDK for **Gaet**, a PostgreSQL database backup and cloud sync CLI tool.

[![npm version](https://img.shields.io/npm/v/@ghanirahmans/gaet.svg)](https://www.npmjs.com/package/@ghanirahmans/gaet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Architecture

```text
 ┌───────────────────────────┐      HTTP REST API       ┌───────────────────────────┐
 │   Your Web Application    │   (http://127.0.0.1:6161) │     Gaet Service Daemon   │
 │   (Next.js / React / Node)├─────────────────────────►│     (gaet serve --auto)   │
 └─────────────┬─────────────┘                          └─────────────┬─────────────┘
               │                                                      │
               │ import { gaet } from '@ghanirahmans/gaet'             │ PostgreSQL Engine
               ▼                                                      ▼
   ┌──────────────────────┐                             ┌───────────────────────────┐
   │  TypeScript SDK      │                             │ Local DB <---> Cloud Remote│
   └──────────────────────┘                             └───────────────────────────┘
```

## Installation

```bash
npm install @ghanirahmans/gaet
# or
pnpm add @ghanirahmans/gaet
# or
yarn add @ghanirahmans/gaet
# or
bun add @ghanirahmans/gaet
```

## Prerequisites

Ensure the `gaet` service daemon is running locally or on your server:

```bash
# Start background server (default port: 6161)
gaet serve

# Or enable auto-start service (systemd, launchd, or Task Scheduler)
gaet serve --auto
```

## Quick Start

```typescript
import { gaet } from '@ghanirahmans/gaet';

// Check connection status
const status = await gaet.status();
console.log('Local DB connected:', status.local_ok);
console.log('Remote Cloud configured:', status.remote_configured);

// Trigger a backup to cloud
const pushResult = await gaet.push();
if (pushResult.ok) {
  console.log('Backup created:', pushResult.snapshot);
}

// List local snapshot dumps
const { snapshots } = await gaet.snapshots();
snapshots.forEach(s => {
  console.log(`${s.filename} (${s.size_mb} MB)`);
});
```

## Code Examples

### Next.js App Router API Route (`app/api/backup/route.ts`)

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
    return NextResponse.json({ error: 'Gaet daemon unreachable: ' + error.message }, { status: 503 });
  }
}
```

### React Component

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
      setStatusMsg('Daemon offline');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={handleBackup} disabled={loading}>
        {loading ? 'Creating Backup...' : 'Push Backup'}
      </button>
      {statusMsg && <p>{statusMsg}</p>}
    </div>
  );
}
```

## Custom Client Options

```typescript
import { GaetClient } from '@ghanirahmans/gaet';

const gaetClient = new GaetClient({
  baseUrl: 'http://127.0.0.1:6161',
  timeout: 120000, // 2 minutes timeout for large database operations
});

const checkResult = await gaetClient.check();
console.log('PostgreSQL tools ok:', checkResult.checks.tools.ok);
```

## API Reference

| Method | Return Type | Description |
| :--- | :--- | :--- |
| `gaet.status()` | `Promise<GaetStatusResponse>` | Returns local and cloud database connection status. |
| `gaet.push()` | `Promise<GaetPushResponse>` | Triggers database backup from local database to cloud remote. |
| `gaet.fetch()` | `Promise<GaetFetchResponse>` | Fetches cloud database state and restores it locally. |
| `gaet.restore(name?)` | `Promise<GaetRestoreResponse>` | Restores database from a local `.dump` snapshot file. |
| `gaet.snapshots()` | `Promise<GaetSnapshotsResponse>` | Lists snapshot files stored in `~/.gaet/backups`. |
| `gaet.deleteSnapshot(name)` | `Promise<GaetGenericResponse>` | Removes a specific snapshot dump file from disk. |
| `gaet.logs()` | `Promise<GaetLogsResponse>` | Reads audit log entries from `~/.gaet/gaet.log`. |
| `gaet.check()` | `Promise<GaetCheckResponse>` | Runs system checks for `pg_dump`, `psql`, and permissions. |
| `gaet.diff()` | `Promise<GaetDiffResponse>` | Compares table counts between local and remote databases. |

## TypeScript Types

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

## License

MIT © [Ghani Rahman](https://github.com/ghanirahmans)
