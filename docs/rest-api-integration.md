# REST API & Sidecar Integration Guide (Next.js, React, Node.js, Python)

`gaet` provides an embedded, zero-dependency REST API server (`gaet serve`) that allows web applications, frameworks, and backend services to programmatically trigger backups, monitor database sync status, and inspect snapshot history.

---

## 1. Starting the REST API Service

Run `gaet serve` in your development environment or server:

```bash
# Start HTTP REST API server on port 6161
gaet serve

# Custom host/port without opening browser automatically
gaet serve --host 127.0.0.1 --port 6161 --no-open

# Register as OS background daemon (systemd / launchd / Task Scheduler)
gaet serve --auto
```

By default, the REST API listens at `http://127.0.0.1:6161`.

---

## 2. CORS & Preflight Support

`gaet serve` includes built-in **CORS middleware** (`Access-Control-Allow-Origin: *`) and handles HTTP `OPTIONS` preflight requests natively. Frontend frameworks running on separate ports (e.g. Next.js on `:3000` or Vite React on `:5173`) can communicate directly with Gaet without CORS restrictions.

---

## 3. REST API Endpoint Reference

### `GET /api/status`
Returns database connection status and table counts.

**Response:**
```json
{
  "local_ok": true,
  "host": "127.0.0.1",
  "port": "5432",
  "user": "postgres",
  "db": "postgres",
  "remote_configured": true,
  "remote_host": "aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
}
```

---

### `POST /api/push`
Triggers a real-time database backup from local database to Cloud Remote DB.

**Response:**
```json
{
  "ok": true,
  "msg": "Backup & push to cloud completed successfully!",
  "snapshot": "gaet_20260817_190000.dump"
}
```

---

### `POST /api/fetch`
Fetches the latest snapshot from Cloud Remote DB and restores it into the local database instance.

**Response:**
```json
{
  "ok": true,
  "msg": "Cloud snapshot restored to local database successfully!"
}
```

---

### `GET /api/snapshots`
Retrieves a list of available local `.dump` snapshots stored in `~/.gaet/backups`.

**Response:**
```json
{
  "count": 3,
  "snapshots": [
    {
      "name": "gaet_20260817_190000.dump",
      "size_mb": 4.25,
      "mod_time": "2026-08-17 19:00:00"
    }
  ]
}
```

---

### `GET /api/logs`
Retrieves structured audit log entries recorded by Gaet (`~/.gaet/gaet.log`).

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2026-08-17T19:00:00Z",
      "command": "push",
      "status": "success",
      "snapshot": "gaet_20260817_190000.dump"
    }
  ]
}
```

---

### `GET /api/check`
Executes preflight diagnostics verifying database client binaries (`pg_dump`, `psql`) and authentication.

**Response:**
```json
{
  "ok": true,
  "checks": {
    "tools": { "ok": true, "pg_dump": "/usr/bin/pg_dump" },
    "local_db": { "ok": true, "host": "127.0.0.1", "port": "5432" },
    "remote_db": { "configured": true, "reachable": true }
  }
}
```

---

## 4. Code Integration Examples

### Next.js (App Router - TypeScript)

Create an API route in Next.js (`app/api/backup/route.ts`):

```typescript
import { NextResponse } from 'next/server';

const GAET_API = process.env.GAET_API_URL || 'http://127.0.0.1:6161';

// Trigger database push from Next.js
export async function POST() {
  try {
    const res = await fetch(`${GAET_API}/api/push`, { method: 'POST' });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json({ ok: false, error: 'Gaet REST service unreachable' }, { status: 500 });
  }
}

// Get DB sync status
export async function GET() {
  const res = await fetch(`${GAET_API}/api/status`);
  const data = await res.json();
  return NextResponse.json(data);
}
```

---

### React / Vite Client (Frontend)

Call Gaet REST API directly from your React component:

```jsx
import React, { useState, useEffect } from 'react';

export function BackupControl() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch('http://127.0.0.1:6161/api/status')
      .then(res => res.json())
      .then(data => setStatus(data));
  }, []);

  const triggerPush = async () => {
    setLoading(true);
    const res = await fetch('http://127.0.0.1:6161/api/push', { method: 'POST' });
    const data = await res.json();
    alert(data.msg);
    setLoading(false);
  };

  return (
    <div>
      <h3>Database Sync Manager</h3>
      <p>Local DB: {status?.local_ok ? 'Connected' : 'Offline'}</p>
      <button onClick={triggerPush} disabled={loading}>
        {loading ? 'Backing up...' : 'Push to Cloud'}
      </button>
    </div>
  );
}
```

---

### Node.js / Express Backend

```javascript
const express = require('express');
const axios = require('axios');
const app = express();

const GAET_URL = 'http://127.0.0.1:6161';

app.post('/admin/backup', async (req, res) => {
  try {
    const response = await axios.post(`${GAET_URL}/api/push`);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: 'Failed to trigger backup service' });
  }
});

app.listen(4000, () => console.log('Admin backend on port 4000'));
```

---

### Python (FastAPI / Requests)

```python
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()
GAET_URL = "http://127.0.0.1:6161"

@app.post("/api/backup/push")
def trigger_backup():
    try:
        response = requests.post(f"{GAET_URL}/api/push", timeout=60)
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Gaet service error: {str(e)}")
```

---

## 5. Security Best Practices

1. **Bind to Localhost by Default**: Keep `gaet serve` listening on `127.0.0.1` unless running inside a protected Docker container network.
2. **Reverse Proxy Protection**: In production environments, place `gaet serve` behind NGINX, Caddy, or your main API gateway with token authentication.
3. **Environment Isolation**: Set `GAET_DASHBOARD_PORT=6161` in `~/.gaet/.env` to customize the port if 6161 is occupied.
