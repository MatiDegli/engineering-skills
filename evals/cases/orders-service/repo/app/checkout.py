"""Checkout: validate an order, price it, store it, and confirm it to the customer."""

import json
import os
import re
import smtplib
from email.message import EmailMessage

from app.db import insert_order

PRICES_CENTS = {"BOOK-1": 1500, "BOOK-2": 2200, "MUG-1": 900, "POSTER-1": 1200}
DISCOUNTS = {"WELCOME10": 10, "FRIENDS15": 15}
TAX_RATES = {"AR": 21, "UY": 22, "CL": 19}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def send_confirmation(email: str, order_id: int, total_cents: int) -> None:
    message = EmailMessage()
    message["From"] = "orders@example.com"
    message["To"] = email
    message["Subject"] = f"Order {order_id} confirmed"
    message.set_content(f"Your order {order_id} totals {total_cents / 100:.2f}.")
    with smtplib.SMTP(os.environ["SMTP_HOST"], timeout=10) as smtp:
        smtp.send_message(message)


def handle_checkout(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("the order must be a JSON object")
    email = str(payload.get("email", "")).strip().lower()
    if not EMAIL.match(email):
        raise ValueError("a valid email is required")
    address = str(payload.get("address", "")).strip()
    if not address:
        raise ValueError("a shipping address is required")
    if len(address) > 300:
        raise ValueError("the shipping address is too long")
    country = str(payload.get("country", "")).upper()
    if country not in TAX_RATES:
        raise ValueError("we do not ship to that country")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("the order needs at least one item")
    if len(items) > 50:
        raise ValueError("an order holds at most 50 lines")

    lines = []
    subtotal = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each item must be an object")
        sku = item.get("sku")
        if sku not in PRICES_CENTS:
            raise ValueError(f"unknown item: {sku}")
        quantity = item.get("quantity")
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise ValueError("quantity must be an integer")
        if quantity < 1 or quantity > 20:
            raise ValueError("quantity must be between 1 and 20")
        line_total = PRICES_CENTS[sku] * quantity
        subtotal += line_total
        lines.append({"sku": sku, "quantity": quantity, "line_cents": line_total})

    code = payload.get("discount_code")
    discount = 0
    if code:
        code = str(code).strip().upper()
        if code not in DISCOUNTS:
            raise ValueError("unknown discount code")
        discount = subtotal * DISCOUNTS[code] // 100
        if code == "WELCOME10" and payload.get("returning_customer"):
            raise ValueError("WELCOME10 is only for first orders")

    taxable = subtotal - discount
    tax = taxable * TAX_RATES[country] // 100
    if taxable >= 5000:
        shipping = 0
    elif country == "AR":
        shipping = 700
    else:
        shipping = 1500
    total = taxable + tax + shipping

    order = {
        "email": email,
        "address": address,
        "country": country,
        "lines": lines,
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "tax_cents": tax,
        "shipping_cents": shipping,
        "total_cents": total,
    }
    order["items_json"] = json.dumps(lines)
    order_id = insert_order(order)
    order["id"] = order_id
    del order["items_json"]

    try:
        send_confirmation(email, order_id, total)
        order["confirmation"] = "sent"
    except (OSError, smtplib.SMTPException):
        order["confirmation"] = "pending"
    return order
