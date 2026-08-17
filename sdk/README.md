# gaet (Official TypeScript / JavaScript SDK)

> Official TypeScript & JavaScript client SDK for **Gaet** — Zero-dependency PostgreSQL Database Backup & Cloud Sync CLI & Service.

[![npm version](https://img.shields.io/npm/v/gaet.svg)](https://www.npmjs.com/package/gaet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Installation

```bash
npm install gaet
# or
pnpm add gaet
# or
yarn add gaet
# or
bun add gaet
```

---

## Prerequisites

Ensure the `gaet` CLI service daemon is running in your environment:

```bash
# Start background dashboard & REST API server (port 6161)
gaet serve

# Or register as auto-starting OS daemon (systemd / launchd / Task Scheduler)
gaet serve --auto
```

---

## Quick Start (Next.js / TypeScript)

```typescript
import { gaet } from 'gaet';

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

## Custom Client Configuration

```typescript
import { GaetClient } from 'gaet';

const gaetClient = new GaetClient({
  baseUrl: 'http://127.0.0.1:6161', // Custom REST API endpoint
  timeout: 120000,                  // 120 seconds timeout for large database backups
});

const checkResult = await gaetClient.check();
console.log('PostgreSQL tools ok:', checkResult.checks.tools.ok);
```

---

## API Reference

| Method | Description | Equivalent CLI Command |
| :--- | :--- | :--- |
| `gaet.status()` | Returns local and cloud DB connectivity & table count alignment. | `gaet status` |
| `gaet.push()` | Triggers a real-time database backup from local DB to Cloud Remote. | `gaet push` |
| `gaet.fetch()` | Fetches cloud database state and restores into local database. | `gaet fetch` |
| `gaet.restore(name?)` | Restores local DB from a specific snapshot file. | `gaet restore` |
| `gaet.snapshots()` | Lists all local `.dump` snapshot files in `~/.gaet/backups`. | `gaet snapshots` |
| `gaet.deleteSnapshot(name)` | Deletes a specific snapshot file from disk. | — |
| `gaet.logs()` | Retrieves structured audit log records (`~/.gaet/gaet.log`). | `gaet log` |
| `gaet.check()` | Executes preflight diagnostics (`pg_dump`, `psql`, auth checks). | `gaet check` |
| `gaet.diff()` | Compares table count schema alignment between Local DB and Cloud DB. | `gaet diff` |

---

## License

MIT © [Ghani Rahman](https://github.com/ghanirahmans)
