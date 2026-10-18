import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  GUEST_FEE_CENTS,
  ValidationError,
  conflicts,
  freeCancellationDeadline,
  holdExpiry,
  quote,
  validateBookingRequest,
} from '../src/rules.ts';
import type { BookingRequest, Room, Slot } from '../src/rules.ts';

const NOW = new Date('2027-03-01T09:00:00Z');
const ROOM: Room = { id: 1, name: 'Ada', capacity: 4, hourlyRateCents: 1800 };

function request(changes: Partial<BookingRequest> = {}): BookingRequest {
  return {
    roomId: 1,
    start: '2027-03-10T10:00:00+01:00',
    end: '2027-03-10T11:30:00+01:00',
    bookerName: 'Ana Pérez',
    bookerEmail: 'Ana.Perez@example.com',
    attendees: ['ana.perez@example.com', 'luis.gomez@example.com'],
    ...changes,
  };
}

function slot(start: string, end: string): Slot {
  return { start: new Date(start), end: new Date(end) };
}

test('a valid request is accepted and its emails are normalized', () => {
  const valid = validateBookingRequest(request({ attendees: [' Luis.Gomez@Example.com '] }), NOW);
  assert.equal(valid.bookerEmail, 'ana.perez@example.com');
  assert.deepEqual(valid.attendees, ['luis.gomez@example.com']);
  assert.equal(valid.slot.start.toISOString(), '2027-03-10T09:00:00.000Z');
});

test('a start in the past is rejected', () => {
  const past = request({ start: '2027-02-28T10:00:00+01:00', end: '2027-02-28T11:00:00+01:00' });
  assert.throws(() => validateBookingRequest(past, NOW), ValidationError);
});

test('an end that is not after the start is rejected', () => {
  const backwards = request({ end: '2027-03-10T09:00:00+01:00' });
  assert.throws(() => validateBookingRequest(backwards, NOW), ValidationError);
});

test('times off the quarter hour are rejected', () => {
  const offGrid = request({ end: '2027-03-10T11:20:00+01:00' });
  assert.throws(() => validateBookingRequest(offGrid, NOW), /quarter hour/);
});

test('a booking longer than eight hours is rejected', () => {
  const long = request({ end: '2027-03-10T18:30:00+01:00' });
  assert.throws(() => validateBookingRequest(long, NOW), ValidationError);
});

test('a booker email that is not an address is rejected', () => {
  assert.throws(() => validateBookingRequest(request({ bookerEmail: 'ana' }), NOW), /bookerEmail/);
});

test('attendees that are not addresses are rejected', () => {
  assert.throws(() => validateBookingRequest(request({ attendees: ['luis'] }), NOW), /attendees/);
});

test('a guest pays the room price plus the booking fee', () => {
  const price = quote(ROOM, slot('2027-03-10T09:00:00Z', '2027-03-10T10:30:00Z'), false);
  assert.equal(price.roomCents, 2700);
  assert.equal(price.feeCents, GUEST_FEE_CENTS);
  assert.equal(price.totalCents, 2900);
});

test('a member gets 20% off the room price and pays no fee', () => {
  const price = quote(ROOM, slot('2027-03-10T09:00:00Z', '2027-03-10T10:30:00Z'), true);
  assert.equal(price.discountCents, 540);
  assert.equal(price.feeCents, 0);
  assert.equal(price.totalCents, 2160);
});

test('a booking that starts inside an existing one conflicts', () => {
  const existing = slot('2027-03-10T09:00:00Z', '2027-03-10T10:00:00Z');
  assert.equal(conflicts(existing, slot('2027-03-10T09:30:00Z', '2027-03-10T10:30:00Z')), true);
});

test('a booking that ends inside an existing one conflicts', () => {
  const existing = slot('2027-03-10T09:00:00Z', '2027-03-10T10:00:00Z');
  assert.equal(conflicts(existing, slot('2027-03-10T08:30:00Z', '2027-03-10T09:30:00Z')), true);
});

test('the same slot conflicts with itself', () => {
  const existing = slot('2027-03-10T09:00:00Z', '2027-03-10T10:00:00Z');
  assert.equal(conflicts(existing, existing), true);
});

test('back-to-back bookings do not conflict', () => {
  const existing = slot('2027-03-10T09:00:00Z', '2027-03-10T10:00:00Z');
  assert.equal(conflicts(existing, slot('2027-03-10T10:00:00Z', '2027-03-10T11:00:00Z')), false);
  assert.equal(conflicts(existing, slot('2027-03-10T08:00:00Z', '2027-03-10T09:00:00Z')), false);
});

test('a hold lasts beyond the moment it is made', () => {
  assert.ok(holdExpiry(NOW).getTime() > NOW.getTime());
});

test('the free cancellation deadline is 18:00 on the day before the booking', () => {
  const deadline = freeCancellationDeadline(new Date(2027, 2, 10, 12, 0));
  assert.equal(deadline.getHours(), 18);
  assert.equal(deadline.getMinutes(), 0);
  assert.equal(deadline.getDate(), 9);
});
