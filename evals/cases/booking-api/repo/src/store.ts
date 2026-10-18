import { readFileSync, readdirSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';

import type { Booking, BookingStatus, Room } from './rules.ts';

const MIGRATIONS = new URL('../migrations/', import.meta.url);

export interface NewBooking {
  roomId: number;
  bookerName: string;
  bookerEmail: string;
  attendees: string[];
  start: Date;
  end: Date;
  holdExpiresAt: Date;
  priceCents: number;
  feeCents: number;
  createdAt: Date;
}

export interface Store {
  db: DatabaseSync;
  listRooms(): Room[];
  findRoom(id: number): Room | undefined;
  listOpenBookings(roomId: number, after: Date): Booking[];
  findBooking(id: number): Booking | undefined;
  insertBooking(draft: NewBooking): Booking;
  confirm(id: number): Booking;
  cancel(id: number, refundCents: number): Booking;
  transaction<T>(work: () => T): T;
  close(): void;
}

type Row = Record<string, string | number | null>;

function migrate(db: DatabaseSync): void {
  db.exec('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)');
  const applied = new Set(db.prepare('SELECT name FROM schema_migrations').all().map((row) => row.name));
  const files = readdirSync(MIGRATIONS).filter((name) => name.endsWith('.sql')).sort();
  for (const name of files) {
    if (applied.has(name)) {
      continue;
    }
    db.exec('BEGIN');
    try {
      db.exec(readFileSync(new URL(name, MIGRATIONS), 'utf8'));
      db.prepare('INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)').run(
        name,
        new Date().toISOString(),
      );
      db.exec('COMMIT');
    } catch (error) {
      db.exec('ROLLBACK');
      throw error;
    }
  }
}

function toRoom(row: Row): Room {
  return {
    id: Number(row.id),
    name: String(row.name),
    capacity: Number(row.capacity),
    hourlyRateCents: Number(row.hourly_rate_cents),
  };
}

function toBooking(row: Row): Booking {
  return {
    id: Number(row.id),
    roomId: Number(row.room_id),
    bookerName: String(row.booker_name),
    bookerEmail: String(row.booker_email),
    attendees: JSON.parse(String(row.attendees)) as string[],
    start: new Date(String(row.starts_at)),
    end: new Date(String(row.ends_at)),
    status: String(row.status) as BookingStatus,
    holdExpiresAt: new Date(String(row.hold_expires_at)),
    priceCents: Number(row.price_cents),
    feeCents: Number(row.fee_cents),
    refundCents: row.refund_cents === null ? null : Number(row.refund_cents),
    createdAt: new Date(String(row.created_at)),
  };
}

export function openStore(path: string): Store {
  const db = new DatabaseSync(path);
  migrate(db);

  const findBooking = (id: number): Booking | undefined => {
    const row = db.prepare('SELECT * FROM bookings WHERE id = ?').get(id) as Row | undefined;
    return row === undefined ? undefined : toBooking(row);
  };
  const reload = (id: number): Booking => {
    const booking = findBooking(id);
    if (booking === undefined) {
      throw new Error(`booking ${id} disappeared`);
    }
    return booking;
  };

  return {
    db,
    listRooms: () => (db.prepare('SELECT * FROM rooms ORDER BY id').all() as Row[]).map(toRoom),
    findRoom(id) {
      const row = db.prepare('SELECT * FROM rooms WHERE id = ?').get(id) as Row | undefined;
      return row === undefined ? undefined : toRoom(row);
    },
    listOpenBookings(roomId, after) {
      const rows = db
        .prepare("SELECT * FROM bookings WHERE room_id = ? AND status <> 'cancelled' AND ends_at > ?")
        .all(roomId, after.toISOString()) as Row[];
      return rows.map(toBooking);
    },
    findBooking,
    insertBooking(draft) {
      const result = db
        .prepare(
          `INSERT INTO bookings (room_id, booker_name, booker_email, attendees, starts_at, ends_at,
             status, hold_expires_at, price_cents, fee_cents, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'held', ?, ?, ?, ?)`,
        )
        .run(
          draft.roomId,
          draft.bookerName,
          draft.bookerEmail,
          JSON.stringify(draft.attendees),
          draft.start.toISOString(),
          draft.end.toISOString(),
          draft.holdExpiresAt.toISOString(),
          draft.priceCents,
          draft.feeCents,
          draft.createdAt.toISOString(),
        );
      return reload(Number(result.lastInsertRowid));
    },
    confirm(id) {
      db.prepare("UPDATE bookings SET status = 'confirmed' WHERE id = ?").run(id);
      return reload(id);
    },
    cancel(id, refundCents) {
      db.prepare("UPDATE bookings SET status = 'cancelled', refund_cents = ? WHERE id = ?").run(refundCents, id);
      return reload(id);
    },
    transaction(work) {
      // BEGIN IMMEDIATE takes the write lock before the first read, so a check and its insert cannot interleave.
      db.exec('BEGIN IMMEDIATE');
      try {
        const result = work();
        db.exec('COMMIT');
        return result;
      } catch (error) {
        db.exec('ROLLBACK');
        throw error;
      }
    },
    close: () => db.close(),
  };
}
