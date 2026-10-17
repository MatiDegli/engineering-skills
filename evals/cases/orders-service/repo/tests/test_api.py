from unittest import mock

import pytest

from app.api import app

SHOP_KEY = "a9f3c2e17b84d05f6e2c9a1b3d7f8e40"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SHOP_API_KEY", SHOP_KEY)
    return app.test_client()


def order_payload():
    return {
        "email": "ana@example.com",
        "address": "1 Test Street",
        "country": "AR",
        "items": [{"sku": "BOOK-1", "quantity": 2}],
    }


def test_create_order(client):
    with mock.patch("app.checkout.insert_order", return_value=7), mock.patch(
        "app.checkout.send_confirmation"
    ):
        response = client.post("/orders", json=order_payload(), headers={"X-Shop-Key": SHOP_KEY})
    assert response.status_code == 201


def test_unknown_item_is_rejected(client):
    payload = order_payload() | {"items": [{"sku": "NOPE", "quantity": 1}]}
    response = client.post("/orders", json=payload, headers={"X-Shop-Key": SHOP_KEY})
    assert response.status_code == 400


def test_requests_without_the_shop_key_are_rejected(client):
    assert client.post("/orders", json=order_payload()).status_code == 401
    assert client.get("/orders/7").status_code == 401
