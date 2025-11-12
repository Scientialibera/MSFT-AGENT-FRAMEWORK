# ============================================================================
# Dockerfile for Fabric Data Agent MCP Server
# Optimized for Azure App Service deployment with HTTP transport
# ============================================================================

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install build and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENABLE_MCP_SERVER=True \
    ENABLE_MCP_HTTP_SERVER=True \
    MCP_HTTP_PORT=8080

# Copy application code
COPY . .

# Copy .env file to the app directory for runtime configuration
COPY foundry_mcp/.env foundry_mcp/.env

# Health check (verify FastMCP HTTP server is responding)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/mcp/ || exit 1

# Expose port for HTTP MCP communication
EXPOSE 8080

# Run the MCP server with HTTP transport enabled
CMD ["python", "-u", "foundry_mcp/app/mcp_server.py"]
