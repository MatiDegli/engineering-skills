"""HTTP routes for placing and reading orders."""

import hmac
import logging
import os

from flask import Flask, jsonify, request

from app.checkout import handle_checkout
from app.db import fetch_order

logger = logging.getLogger("orders")
app = Flask(__name__)


def shop_key_valid() -> bool:
    expected = os.environ.get("SHOP_API_KEY", "")
    supplied = request.headers.get("X-Shop-Key", "")
    return bool(expected) and hmac.compare_digest(supplied, expected)


@app.post("/orders")
def create_order():
    if not shop_key_valid():
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(force=True)
    logger.info("order received: %s", payload)
    try:
        order = handle_checkout(payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(order), 201


@app.get("/orders/<int:order_id>")
def get_order(order_id: int):
    if not shop_key_valid():
        return jsonify({"error": "unauthorized"}), 401
    order = fetch_order(order_id)
    if order is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(order)
