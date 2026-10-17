"""Database access for orders."""

import logging
import os

import psycopg

logger = logging.getLogger("orders")


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5)


def insert_order(order: dict) -> int:
    params = (order["email"], order["address"], order["total_cents"], order["items_json"])
    try:
        with connect() as connection:
            row = connection.execute(
                "INSERT INTO orders (email, address, total_cents, items)"
                " VALUES (%s, %s, %s, %s) RETURNING id",
                params,
            ).fetchone()
            return row[0]
    except Exception as error:
        logger.error("insert failed: %s params=%s", error, params)
        raise


def fetch_order(order_id: int) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id, email, address, total_cents, items FROM orders WHERE id = %s", (order_id,)
        ).fetchone()
    if row is None:
        return None
    keys = ("id", "email", "address", "total_cents", "items")
    return dict(zip(keys, row, strict=True))
