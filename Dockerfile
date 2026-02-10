# Gondola v2.2 - AI Coding Assistant
# Built by a Vandal Architect

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for persistence
RUN mkdir -p /app/logs /app/.gondola_knowledge

# Expose port for Web UI
EXPOSE 5040

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5040/health')" || exit 1

# Default command - run Web UI
CMD ["python", "venice-web-ui/server.py"]
