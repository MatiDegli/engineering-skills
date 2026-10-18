CREATE TABLE rooms (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    hourly_rate_cents INTEGER NOT NULL CHECK (hourly_rate_cents >= 0)
);

CREATE TABLE members (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    joined_on TEXT NOT NULL
);

CREATE TABLE bookings (
    id INTEGER PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms (id),
    booker_name TEXT NOT NULL,
    booker_email TEXT NOT NULL,
    attendees TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('held', 'confirmed', 'cancelled')),
    hold_expires_at TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    fee_cents INTEGER NOT NULL CHECK (fee_cents >= 0),
    refund_cents INTEGER,
    created_at TEXT NOT NULL,
    CHECK (ends_at > starts_at)
);

CREATE INDEX bookings_by_room ON bookings (room_id, ends_at);

INSERT INTO rooms (id, name, capacity, hourly_rate_cents) VALUES
    (1, 'Ada', 4, 1800),
    (2, 'Turing', 8, 3200),
    (3, 'Lovelace', 12, 4800);
