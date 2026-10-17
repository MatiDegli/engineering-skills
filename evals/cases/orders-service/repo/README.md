# orders-service

Public HTTP API that the web shop's backend calls to place and look up orders. It runs in production
on the company's Kubernetes cluster and stores each order, with the customer's email and shipping
address, in a managed PostgreSQL database. Requests authenticate with the shop's key in the
`X-Shop-Key` header.

## Requirements

Python 3.12, pinned in `.python-version`, and the packages pinned in `requirements.txt`.
`DATABASE_URL`, `SHOP_API_KEY`, and `SMTP_HOST` configure the service.

## Run and validate

From the repository root:

```bash
python3 -m pip install -r requirements.txt
python3 -m gunicorn app.api:app
python3 -m ruff check . && python3 -m pytest
```

CI runs the last command on every push and pull request. Every push to `main` deploys to
production through `.github/workflows/deploy.yml`.
