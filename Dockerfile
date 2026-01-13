FROM python:3.11-slim

# Install system dependencies (including curl for health checks)
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
ENV UV_HTTP_TIMEOUT=600
ENV UV_REQUEST_TIMEOUT=600
RUN uv sync --frozen --no-dev --refresh

# Create keys directory
RUN mkdir -p /app/keys

# Run as non-root user
RUN useradd -m -u 1000 okta && chown -R okta:okta /app
USER okta

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Expose HTTP port for SSE transport
EXPOSE 8080

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD sh -c "curl -f --silent --max-time 2 http://localhost:${MCP_PORT:-8080}/sse | head -c 1 > /dev/null"

# Run the MCP server
CMD [".venv/bin/python", "-m", "okta_mcp_server.server"]
