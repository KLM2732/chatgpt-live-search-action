FROM python:3.11-slim

WORKDIR /app

# System deps for trafilatura (lxml etc.)
RUN apt-get update && apt-get install -y build-essential libxml2-dev libxslt1-dev libffi-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Use gunicorn/uvicorn worker
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
