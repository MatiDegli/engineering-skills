# booking-api

HTTP API that the member portal of the Nube Cowork space calls to book its meeting rooms. It runs in
production as one container on the space's own host and keeps the rooms, the members, and the
bookings in a SQLite database: the booker's name and email, the attendees' emails, and each member's
name and email. Requests authenticate with the portal's key in the `X-Api-Key` header.

## Requirements

Node 24. The service has no packages to install: it uses only `node:http`, `node:sqlite`, and
`node:test`, and Node removes the TypeScript types when it loads a file. `tsconfig.json` configures
editors; there is no build step. `BOOKING_API_KEY` (at least 16 characters) is required. `PORT`
(default 8080) and `DATABASE_PATH` (default `./data/booking.db`) are optional.

## Run and validate

From the repository root:

```bash
BOOKING_API_KEY=local-dev-secret-key node src/main.ts
node --test
```

CI runs the second command on every push and pull request. The container keeps its database in the
`/data` volume. At start, `src/store.ts` applies the files of `migrations/` that
`schema_migrations` does not list yet, in name order. `GET /health` answers without a key, and each
request writes one JSON line to the log with its method, path, status, and duration.

## Business rules

- A booking is for one room. It starts and ends on the quarter hour, lasts between 30 minutes and 8
  hours, and starts in the future. Times are ISO 8601 instants with a UTC offset.
- The price is the room's hourly rate for the booked time. Members get 20% off. Membership is looked
  up by email in the `members` table.
- Guests, who are the bookers that are not members, also pay a booking fee of 2.00 EUR. The fee is
  non-refundable: it stays with Nube Cowork when a booking is cancelled, even before the free
  cancellation deadline.
- A new booking is a hold. It reserves the room for 10 minutes before payment. The portal confirms
  the booking once the payment succeeds, and an unpaid hold expires and frees the room.
- A room never has two overlapping bookings. Confirmed bookings and holds that have not expired
  count; cancelled bookings and expired holds do not.
- Attendees are an array of email addresses, from one up to the room's capacity.
- Cancellation is free until 18:00 Europe/Madrid time on the day before the booking starts. Until
  then, cancelling a confirmed booking refunds what was paid except the fee. After that deadline it
  releases the room and refunds nothing.

## API

All bodies are JSON. Prices are in euro cents.

| Request | Answer |
| --- | --- |
| `GET /rooms` | The rooms with their `capacity` and `hourlyRateCents` |
| `POST /bookings` | `201` with the held booking, its `priceCents`, `feeCents`, and `holdExpiresAt` |
| `POST /bookings/:id/confirm` | `200` with the confirmed booking; confirming twice changes nothing |
| `DELETE /bookings/:id` | `200` with the cancelled booking and its `refundCents` |

`POST /bookings` takes `roomId`, `start`, `end`, `bookerName`, `bookerEmail`, and `attendees`:

```json
{
  "roomId": 1,
  "start": "2027-03-10T10:00:00+01:00",
  "end": "2027-03-10T11:30:00+01:00",
  "bookerName": "Luis Gómez",
  "bookerEmail": "luis.gomez@example.com",
  "attendees": ["luis.gomez@example.com", "marta.ruiz@example.com"]
}
```

Errors answer `{"error": "..."}` with `400` for an invalid request, `401` for a missing or wrong key,
`404` for an unknown room or booking, and `409` when the room is taken, a hold has expired, or the
booking was already cancelled.
