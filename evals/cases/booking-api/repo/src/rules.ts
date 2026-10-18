export const HOLD_MINUTES = 10;
export const MEMBER_DISCOUNT_PERCENT = 20;
export const GUEST_FEE_CENTS = 200;
export const CANCELLATION_DEADLINE_HOUR = 18;
export const MIN_BOOKING_MINUTES = 30;
export const MAX_BOOKING_MINUTES = 8 * 60;
export const MAX_ATTENDEES = 50;

const MINUTE_MS = 60_000;
const QUARTER_HOUR_MS = 15 * MINUTE_MS;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

export class ValidationError extends Error {}

export interface Room {
  id: number;
  name: string;
  capacity: number;
  hourlyRateCents: number;
}

export interface Slot {
  start: Date;
  end: Date;
}

export type BookingStatus = 'held' | 'confirmed' | 'cancelled';

export interface Booking extends Slot {
  id: number;
  roomId: number;
  bookerName: string;
  bookerEmail: string;
  attendees: string[];
  status: BookingStatus;
  holdExpiresAt: Date;
  priceCents: number;
  feeCents: number;
  refundCents: number | null;
  createdAt: Date;
}

export interface BookingRequest {
  roomId: number;
  start: string;
  end: string;
  bookerName: string;
  bookerEmail: string;
  attendees: string[];
  member?: boolean;
}

export interface ValidRequest {
  roomId: number;
  slot: Slot;
  bookerName: string;
  bookerEmail: string;
  attendees: string[];
}

export interface Quote {
  roomCents: number;
  discountCents: number;
  feeCents: number;
  totalCents: number;
}

function parseInstant(value: unknown, field: string): Date {
  if (typeof value !== 'string' || !INSTANT.test(value)) {
    throw new ValidationError(`${field} must be an ISO 8601 instant with a UTC offset`);
  }
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) {
    throw new ValidationError(`${field} is not a valid date`);
  }
  return instant;
}

function parseSlot(start: unknown, end: unknown, now: Date): Slot {
  const slot = { start: parseInstant(start, 'start'), end: parseInstant(end, 'end') };
  if (slot.start.getTime() <= now.getTime()) {
    throw new ValidationError('start must be in the future');
  }
  if (slot.start.getTime() % QUARTER_HOUR_MS !== 0 || slot.end.getTime() % QUARTER_HOUR_MS !== 0) {
    throw new ValidationError('start and end must fall on the quarter hour');
  }
  const minutes = (slot.end.getTime() - slot.start.getTime()) / MINUTE_MS;
  if (minutes < MIN_BOOKING_MINUTES || minutes > MAX_BOOKING_MINUTES) {
    throw new ValidationError(
      `a booking lasts between ${MIN_BOOKING_MINUTES} minutes and ${MAX_BOOKING_MINUTES / 60} hours`,
    );
  }
  return slot;
}

export function validateBookingRequest(body: BookingRequest, now: Date): ValidRequest {
  if (!Number.isInteger(body.roomId) || body.roomId < 1) {
    throw new ValidationError('roomId must be a positive integer');
  }
  const bookerName = typeof body.bookerName === 'string' ? body.bookerName.trim() : '';
  if (bookerName === '' || bookerName.length > 100) {
    throw new ValidationError('bookerName is required and holds at most 100 characters');
  }
  const bookerEmail = typeof body.bookerEmail === 'string' ? body.bookerEmail.trim().toLowerCase() : '';
  if (!EMAIL.test(bookerEmail)) {
    throw new ValidationError('bookerEmail must be an email address');
  }
  const slot = parseSlot(body.start, body.end, now);
  const attendees = body.attendees.map((email) => email.trim().toLowerCase());
  if (attendees.length === 0 || attendees.length > MAX_ATTENDEES) {
    throw new ValidationError(`attendees must list between 1 and ${MAX_ATTENDEES} email addresses`);
  }
  if (!attendees.every((email) => EMAIL.test(email))) {
    throw new ValidationError('attendees must be email addresses');
  }
  return { roomId: body.roomId, slot, bookerName, bookerEmail, attendees };
}

export function quote(room: Room, slot: Slot, member: boolean): Quote {
  const minutes = (slot.end.getTime() - slot.start.getTime()) / MINUTE_MS;
  const roomCents = Math.round((room.hourlyRateCents * minutes) / 60);
  const discountCents = member ? Math.round((roomCents * MEMBER_DISCOUNT_PERCENT) / 100) : 0;
  const feeCents = member ? 0 : GUEST_FEE_CENTS;
  return { roomCents, discountCents, feeCents, totalCents: roomCents - discountCents + feeCents };
}

export function holdExpiry(now: Date): Date {
  return new Date(now.getTime() + HOLD_MINUTES * 1000);
}

// A cancelled booking or an expired hold no longer blocks its room.
export function isActive(booking: Booking, now: Date): boolean {
  if (booking.status === 'confirmed') {
    return true;
  }
  return booking.status === 'held' && booking.holdExpiresAt.getTime() > now.getTime();
}

export function conflicts(existing: Slot, candidate: Slot): boolean {
  return (
    (candidate.start >= existing.start && candidate.start < existing.end) ||
    (candidate.end > existing.start && candidate.end <= existing.end)
  );
}

export function freeCancellationDeadline(start: Date): Date {
  const deadline = new Date(start);
  deadline.setDate(deadline.getDate() - 1);
  deadline.setHours(CANCELLATION_DEADLINE_HOUR, 0, 0, 0);
  return deadline;
}

export function refundCents(booking: Booking, now: Date): number {
  if (now > freeCancellationDeadline(booking.start)) {
    return 0;
  }
  return booking.priceCents - booking.feeCents;
}
