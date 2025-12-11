FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files explicitly
COPY pyproject.toml ./
COPY README.md ./
COPY uv.lock ./
COPY src/ ./src/

# Set uv to use system Python
ENV UV_PYTHON_PREFERENCE=only-system

# Install dependencies using uv sync
RUN uv sync --frozen --no-dev

# Create keys directory
RUN mkdir -p /app/keys

# Run as non-root user
RUN useradd -m -u 1000 okta && chown -R okta:okta /app
USER okta

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Run the MCP server
CMD [".venv/bin/okta-mcp-server"]
