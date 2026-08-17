import test from 'node:test';
import assert from 'node:assert/strict';
import { GaetClient, gaet } from '../dist/index.js';

test('GaetClient initialization with default options', () => {
  const client = new GaetClient();
  assert.ok(client instanceof GaetClient);
  assert.ok(gaet instanceof GaetClient);
});

test('GaetClient initialization with custom baseUrl', () => {
  const client = new GaetClient({ baseUrl: 'http://localhost:9999' });
  assert.ok(client instanceof GaetClient);
});

test('GaetClient handles mock fetch request', async () => {
  const mockFetch = async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:6161/api/status');
    return {
      ok: true,
      status: 200,
      json: async () => ({
        local_ok: true,
        host: '127.0.0.1',
        port: '5432',
        user: 'postgres',
        db: 'postgres',
        remote_configured: true,
        remote_host: 'cloud-db:5432/postgres',
      }),
    };
  };

  const client = new GaetClient({ fetch: mockFetch });
  const status = await client.status();

  assert.equal(status.local_ok, true);
  assert.equal(status.db, 'postgres');
  assert.equal(status.remote_configured, true);
});

test('startServer detects when daemon is already running', async () => {
  const mockFetch = async (url) => {
    return {
      ok: true,
      status: 200,
      json: async () => ({ local_ok: true }),
    };
  };

  const client = new GaetClient({ fetch: mockFetch });
  const res = await client.startServer();
  assert.equal(res.ok, true);
  assert.equal(res.msg, 'Gaet service daemon is already running.');
});

test('stopServer gracefully handles unspawned process', async () => {
  const client = new GaetClient();
  const res = await client.stopServer();
  assert.equal(res.ok, true);
  assert.equal(res.msg, 'No active spawned Gaet process to stop.');
});
