import { createHash, timingSafeEqual } from 'node:crypto';
import { createServer } from 'node:http';
import type { IncomingMessage, Server, ServerResponse } from 'node:http';

import { ConflictError, NotFoundError, cancelBooking, confirmBooking, createHold } from './bookings.ts';
import { ValidationError } from './rules.ts';
import type { Booking, BookingRequest } from './rules.ts';
import type { Store } from './store.ts';

export interface AppOptions {
  store: Store;
  apiKey: string;
  clock?: () => Date;
  log?: (line: string) => void;
}

interface Reply {
  status: number;
  body: unknown;
}

const BOOKING_PATH = /^\/bookings\/(\d+)(\/confirm)?$/;

function digest(value: string): Buffer {
  return createHash('sha256').update(value).digest();
}

function authorized(request: IncomingMessage, apiKey: string): boolean {
  const supplied = request.headers['x-api-key'];
  return typeof supplied === 'string' && timingSafeEqual(digest(supplied), digest(apiKey));
}

async function readJson(request: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(chunk as Buffer);
  }
  let body: unknown;
  try {
    body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new ValidationError('the body must be valid JSON');
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body)) {
    throw new ValidationError('the body must be a JSON object');
  }
  return body as Record<string, unknown>;
}

function toJson(booking: Booking) {
  return {
    id: booking.id,
    roomId: booking.roomId,
    status: booking.status,
    start: booking.start.toISOString(),
    end: booking.end.toISOString(),
    bookerName: booking.bookerName,
    bookerEmail: booking.bookerEmail,
    attendees: booking.attendees,
    priceCents: booking.priceCents,
    feeCents: booking.feeCents,
    holdExpiresAt: booking.holdExpiresAt.toISOString(),
    refundCents: booking.refundCents,
  };
}

async function route(request: IncomingMessage, path: string, options: AppOptions): Promise<Reply> {
  const now = (options.clock ?? (() => new Date()))();
  const method = request.method ?? 'GET';
  if (method === 'GET' && path === '/health') {
    return { status: 200, body: { status: 'ok' } };
  }
  if (!authorized(request, options.apiKey)) {
    return { status: 401, body: { error: 'unauthorized' } };
  }
  if (method === 'GET' && path === '/rooms') {
    return { status: 200, body: options.store.listRooms() };
  }
  if (method === 'POST' && path === '/bookings') {
    const body = await readJson(request);
    return { status: 201, body: toJson(createHold(options.store, body as unknown as BookingRequest, now)) };
  }
  const match = BOOKING_PATH.exec(path);
  if (match !== null) {
    const id = Number(match[1]);
    if (method === 'POST' && match[2] !== undefined) {
      return { status: 200, body: toJson(confirmBooking(options.store, id, now)) };
    }
    if (method === 'DELETE' && match[2] === undefined) {
      return { status: 200, body: toJson(cancelBooking(options.store, id, now)) };
    }
  }
  return { status: 404, body: { error: 'not found' } };
}

function failure(error: unknown): Reply {
  if (error instanceof ValidationError) {
    return { status: 400, body: { error: error.message } };
  }
  if (error instanceof NotFoundError) {
    return { status: 404, body: { error: error.message } };
  }
  if (error instanceof ConflictError) {
    return { status: 409, body: { error: error.message } };
  }
  console.error(error);
  return { status: 500, body: { error: 'internal error' } };
}

export function createApp(options: AppOptions): Server {
  return createServer(async (request: IncomingMessage, response: ServerResponse) => {
    const started = Date.now();
    const path = new URL(request.url ?? '/', 'http://localhost').pathname;
    let reply: Reply;
    try {
      reply = await route(request, path, options);
    } catch (error) {
      reply = failure(error);
    }
    response.writeHead(reply.status, { 'content-type': 'application/json' });
    response.end(JSON.stringify(reply.body));
    (options.log ?? console.log)(
      JSON.stringify({ method: request.method, path, status: reply.status, ms: Date.now() - started }),
    );
  });
}
