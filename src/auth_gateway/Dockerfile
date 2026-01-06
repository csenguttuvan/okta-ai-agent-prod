FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy gateway code
COPY gateway.py .

# Expose port
EXPOSE 9000

# Run gateway
CMD ["python", "gateway.py"]
