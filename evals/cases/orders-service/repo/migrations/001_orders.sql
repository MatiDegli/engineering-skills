CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    address TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    items JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
