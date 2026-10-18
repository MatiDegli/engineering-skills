import assert from 'node:assert/strict';
import type { AddressInfo } from 'node:net';
import { after, before, beforeEach, test } from 'node:test';

import { createApp } from '../src/server.ts';
import { openStore } from '../src/store.ts';

const NOW = new Date('2027-03-01T09:00:00Z');
const KEY = 'test-key';
const MEMBER_EMAIL = 'ana.perez@example.com';

const store = openStore(':memory:');
let now = new Date(NOW);
const server = createApp({ store, apiKey: KEY, clock: () => now, log: () => {} });
let base = '';

before(async () => {
  const insertMember = store.db.prepare('INSERT INTO members (email, name, joined_on) VALUES (?, ?, ?)');
  insertMember.run(MEMBER_EMAIL, 'Ana Pérez', '2026-01-15');
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

after(() => {
  server.closeAllConnections();
  server.close();
  store.close();
});

beforeEach(() => {
  now = new Date(NOW);
  store.db.exec('DELETE FROM bookings');
});

interface BookingBody {
  id: number;
  status: string;
  priceCents: number;
  feeCents: number;
  holdExpiresAt: string;
  refundCents: number | null;
  error: string;
}

async function call<T = BookingBody>(method: string, path: string, body?: unknown, key: string | null = KEY) {
  const response = await fetch(base + path, {
    method,
    headers: key === null ? {} : { 'x-api-key': key },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: response.status, body: (await response.json()) as T };
}

function booking(changes: Record<string, unknown> = {}) {
  return {
    roomId: 1,
    start: '2027-03-10T10:00:00+01:00',
    end: '2027-03-10T11:30:00+01:00',
    bookerName: 'Luis Gómez',
    bookerEmail: 'luis.gomez@example.com',
    attendees: ['luis.gomez@example.com', 'marta.ruiz@example.com'],
    ...changes,
  };
}

test('health answers without a key', async () => {
  const reply = await call<{ status: string }>('GET', '/health', undefined, null);
  assert.equal(reply.status, 200);
  assert.equal(reply.body.status, 'ok');
});

test('every other route needs the key', async () => {
  assert.equal((await call('GET', '/rooms', undefined, null)).status, 401);
  assert.equal((await call('GET', '/rooms', undefined, 'wrong-key')).status, 401);
});

test('rooms are listed with their capacity and rate', async () => {
  const reply = await call<unknown[]>('GET', '/rooms');
  assert.equal(reply.status, 200);
  assert.equal(reply.body.length, 3);
  assert.deepEqual(reply.body[0], { id: 1, name: 'Ada', capacity: 4, hourlyRateCents: 1800 });
});

test('a guest booking is held with the booking fee', async () => {
  const reply = await call('POST', '/bookings', booking());
  assert.equal(reply.status, 201);
  assert.equal(reply.body.status, 'held');
  assert.equal(reply.body.priceCents, 2900);
  assert.equal(reply.body.feeCents, 200);
  assert.ok(new Date(reply.body.holdExpiresAt) > now);
});

test('a member booking gets 20% off and no fee', async () => {
  const reply = await call('POST', '/bookings', booking({ bookerEmail: MEMBER_EMAIL, member: true }));
  assert.equal(reply.status, 201);
  assert.equal(reply.body.priceCents, 2160);
  assert.equal(reply.body.feeCents, 0);
});

test('an invalid booking is answered with 400', async () => {
  const reply = await call('POST', '/bookings', booking({ bookerEmail: 'luis' }));
  assert.equal(reply.status, 400);
  assert.match(reply.body.error, /bookerEmail/);
});

test('a body that is not JSON is answered with 400', async () => {
  const response = await fetch(`${base}/bookings`, { method: 'POST', headers: { 'x-api-key': KEY }, body: '{' });
  assert.equal(response.status, 400);
});

test('an unknown room is answered with 404', async () => {
  assert.equal((await call('POST', '/bookings', booking({ roomId: 99 }))).status, 404);
});

test('more attendees than the room holds are answered with 400', async () => {
  const crowd = ['a', 'b', 'c', 'd', 'e'].map((name) => `${name}@example.com`);
  assert.equal((await call('POST', '/bookings', booking({ attendees: crowd }))).status, 400);
});

test('a booking that overlaps an existing one is answered with 409', async () => {
  assert.equal((await call('POST', '/bookings', booking())).status, 201);
  const overlapping = booking({ start: '2027-03-10T11:00:00+01:00', end: '2027-03-10T12:00:00+01:00' });
  assert.equal((await call('POST', '/bookings', overlapping)).status, 409);
});

test('back-to-back bookings of one room and parallel bookings of two rooms are accepted', async () => {
  assert.equal((await call('POST', '/bookings', booking())).status, 201);
  const next = booking({ start: '2027-03-10T11:30:00+01:00', end: '2027-03-10T12:30:00+01:00' });
  assert.equal((await call('POST', '/bookings', next)).status, 201);
  assert.equal((await call('POST', '/bookings', booking({ roomId: 2 }))).status, 201);
});

test('an unpaid hold releases the room once it expires', async () => {
  assert.equal((await call('POST', '/bookings', booking())).status, 201);
  now = new Date(now.getTime() + 11 * 60_000);
  assert.equal((await call('POST', '/bookings', booking())).status, 201);
});

test('a booking is confirmed once, and confirming again changes nothing', async () => {
  const held = await call('POST', '/bookings', booking());
  const first = await call('POST', `/bookings/${held.body.id}/confirm`);
  const second = await call('POST', `/bookings/${held.body.id}/confirm`);
  assert.equal(first.status, 200);
  assert.equal(first.body.status, 'confirmed');
  assert.equal(second.status, 200);
  assert.equal(second.body.status, 'confirmed');
});

test('an expired hold cannot be confirmed', async () => {
  const held = await call('POST', '/bookings', booking());
  now = new Date(now.getTime() + 11 * 60_000);
  assert.equal((await call('POST', `/bookings/${held.body.id}/confirm`)).status, 409);
});

test('the guest booking fee is not refunded when a booking is cancelled before the deadline', async () => {
  const held = await call('POST', '/bookings', booking());
  await call('POST', `/bookings/${held.body.id}/confirm`);
  const cancelled = await call('DELETE', `/bookings/${held.body.id}`);
  assert.equal(cancelled.status, 200);
  assert.equal(cancelled.body.status, 'cancelled');
  assert.equal(cancelled.body.priceCents, 2900);
  assert.equal(cancelled.body.refundCents, 2700);
});

test('cancelling after the deadline refunds nothing', async () => {
  const held = await call('POST', '/bookings', booking());
  await call('POST', `/bookings/${held.body.id}/confirm`);
  now = new Date('2027-03-10T07:00:00Z');
  const cancelled = await call('DELETE', `/bookings/${held.body.id}`);
  assert.equal(cancelled.status, 200);
  assert.equal(cancelled.body.refundCents, 0);
});

test('a cancelled booking frees its room', async () => {
  const held = await call('POST', '/bookings', booking());
  await call('DELETE', `/bookings/${held.body.id}`);
  assert.equal((await call('DELETE', `/bookings/${held.body.id}`)).status, 409);
  assert.equal((await call('POST', '/bookings', booking())).status, 201);
});

test('an unknown booking is answered with 404', async () => {
  assert.equal((await call('DELETE', '/bookings/404')).status, 404);
  assert.equal((await call('POST', '/bookings/404/confirm')).status, 404);
});
