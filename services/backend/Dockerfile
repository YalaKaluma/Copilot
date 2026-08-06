# Production Dockerfile for Backend
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install uv

# Copy shared packages
COPY packages/ /packages/

# Copy application code
COPY services/backend/app/ ./
COPY services/backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Add packages to Python path
ENV PYTHONPATH=/

# Install Python dependencies (production only)
RUN uv sync --frozen --no-dev

RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create app user, but keep runtime as root so entrypoint can fix mounted volume permissions
# before dropping privileges.
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /sandbox/data /sandbox/jobs

# Set environment to prevent uv from downloading anything at runtime
ENV UV_NO_SYNC=1

# Expose the default local port. Railway provides PORT at runtime.
EXPOSE 8080

# Use entrypoint for migrations
ENTRYPOINT ["docker-entrypoint.sh"]

# Production command - use python directly from venv to avoid uv downloading packages
CMD ["/bin/sh", "-c", "exec .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --loop asyncio"]
