FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "app.api:app"]
