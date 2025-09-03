# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Install system dependencies for nsjail and required libraries
RUN apt-get update && apt-get install -y \
    # Build tools
    build-essential \
    pkg-config \
    # nsjail dependencies
    libnl-route-3-dev \
    libnl-3-dev \
    libprotobuf-dev \
    protobuf-compiler \
    autoconf \
    bison \
    flex \
    git \
    # Additional system libraries for Python packages
    libffi-dev \
    libssl-dev \
    # For curl health checks
    curl \
    # Clean up to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Install nsjail from source
RUN git clone https://github.com/google/nsjail.git /tmp/nsjail && \
    cd /tmp/nsjail && \
    make && \
    cp nsjail /usr/local/bin/ && \
    rm -rf /tmp/nsjail

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy nsjail configuration for cloud environment
COPY nsjail.local.cfg /etc/nsjail.cfg

# Create necessary directories with proper permissions
RUN mkdir -p /tmp /sandbox/tmp && \
    chmod 755 /tmp /sandbox /sandbox/tmp

# Set environment variables
ENV BUILD=local
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["python", "main.py"]