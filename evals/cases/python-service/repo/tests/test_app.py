import requests

from inventory.app import create_app


def test_set_stock():
    client = create_app().test_client()
    client.post("/stock/abc", json={"count": 3})
    assert client.get("/stock/abc").json["count"] == 3


def test_warehouse_is_up():
    assert requests.get("https://warehouse.example.com/health").status_code == 200
