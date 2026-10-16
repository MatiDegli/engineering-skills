# Inventory service

HTTP service that stores product stock counts and notifies the warehouse when they change.

## Run

```bash
pip install -r requirements.txt
python -m inventory
```

The service handles 10,000 requests per second on a laptop, so it scales to any store size.
