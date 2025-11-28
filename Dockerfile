# Use a slim Python base image
FROM python:3.11-slim

# Install system dependencies (if needed later, keep minimal for now)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv (Python package manager / runner)
RUN pip install --no-cache-dir uv

# Copy dependency file(s) and install dependencies
# If you have pyproject.toml + uv.lock:
# COPY pyproject.toml uv.lock ./
# RUN uv sync --no-dev

# If you use requirements.txt instead, use this:
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/

# Environment variables (non‑secret defaults; real values come from runtime env)
ENV OKTA_LOG_LEVEL=INFO

# Expose no ports by default (MCP communicates over stdio, not HTTP)
# EXPOSE 8000  # uncomment if you later add an HTTP health endpoint

# Default command to run the MCP server
CMD ["uv", "run", "okta-mcp-server"]
