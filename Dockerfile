FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src:/app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY contracts /app/contracts
COPY docs /app/docs
COPY sample_data /app/sample_data
COPY sql /app/sql
COPY src /app/src
COPY code_fetch_vaddhiparthy.py demo_api.py /app/

EXPOSE 8075

CMD ["uvicorn", "demo_api:app", "--host", "0.0.0.0", "--port", "8075"]
