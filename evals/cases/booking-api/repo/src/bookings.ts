import {
  ValidationError,
  conflicts,
  holdExpiry,
  isActive,
  quote,
  refundCents,
  validateBookingRequest,
} from './rules.ts';
import type { Booking, BookingRequest } from './rules.ts';
import type { Store } from './store.ts';

export class NotFoundError extends Error {}
export class ConflictError extends Error {}

export function createHold(store: Store, body: BookingRequest, now: Date): Booking {
  const request = validateBookingRequest(body, now);
  return store.transaction(() => {
    const room = store.findRoom(request.roomId);
    if (room === undefined) {
      throw new NotFoundError('room not found');
    }
    if (request.attendees.length > room.capacity) {
      throw new ValidationError(`${room.name} holds at most ${room.capacity} attendees`);
    }
    const taken = store.listOpenBookings(room.id, now).filter((booking) => isActive(booking, now));
    if (taken.some((booking) => conflicts(booking, request.slot))) {
      throw new ConflictError('the room is already booked for that time');
    }
    const member = body.member === true;
    const price = quote(room, request.slot, member);
    return store.insertBooking({
      roomId: room.id,
      bookerName: request.bookerName,
      bookerEmail: request.bookerEmail,
      attendees: request.attendees,
      start: request.slot.start,
      end: request.slot.end,
      holdExpiresAt: holdExpiry(now),
      priceCents: price.totalCents,
      feeCents: price.feeCents,
      createdAt: now,
    });
  });
}

export function confirmBooking(store: Store, id: number, now: Date): Booking {
  return store.transaction(() => {
    const booking = store.findBooking(id);
    if (booking === undefined) {
      throw new NotFoundError('booking not found');
    }
    if (booking.status === 'confirmed') {
      return booking;
    }
    if (booking.status === 'cancelled') {
      throw new ConflictError('the booking was cancelled');
    }
    if (booking.holdExpiresAt.getTime() <= now.getTime()) {
      throw new ConflictError('the hold has expired');
    }
    return store.confirm(booking.id);
  });
}

export function cancelBooking(store: Store, id: number, now: Date): Booking {
  return store.transaction(() => {
    const booking = store.findBooking(id);
    if (booking === undefined) {
      throw new NotFoundError('booking not found');
    }
    if (booking.status === 'cancelled') {
      throw new ConflictError('the booking is already cancelled');
    }
    if (booking.start.getTime() <= now.getTime()) {
      throw new ConflictError('the booking has already started');
    }
    const refund = booking.status === 'confirmed' ? refundCents(booking, now) : 0;
    return store.cancel(booking.id, refund);
  });
}
