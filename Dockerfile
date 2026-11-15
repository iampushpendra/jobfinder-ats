FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code (templates live in app/templates, static at the repo root)
COPY app/ ./app/
COPY static/ ./static/

# Expose port
EXPOSE 8080

# Run the app
CMD ["python3", "-m", "app"]
