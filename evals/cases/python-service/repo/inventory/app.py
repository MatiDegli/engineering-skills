import requests
from flask import Flask, request

from inventory import settings

STOCK = {}


def create_app():
    app = Flask(__name__)

    @app.post("/stock/<sku>")
    def set_stock(sku):
        try:
            count = int(request.get_json()["count"])
            STOCK[sku] = count
            notify_warehouse(sku, count)
        except Exception:
            pass
        return {"sku": sku, "count": STOCK.get(sku)}

    @app.get("/stock/<sku>")
    def get_stock(sku):
        return {"sku": sku, "count": STOCK.get(sku, 0)}

    return app


def notify_warehouse(sku, count):
    requests.post(f"{settings.WAREHOUSE_URL}/notify", json={"sku": sku, "count": count})
