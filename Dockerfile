# Use a multi-arch compatible base image
FROM python:3.11-slim as builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /install

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies to a staging directory
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# --- Final Production Image ---
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (FFmpeg is critical for OCI VPS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp_uploads logs

# Default environment variables
ENV ENVIRONMENT=production \
    PORT=8000

# Expose API port
EXPOSE 8000

# Metadata
LABEL maintainer="Nebulyze Team" \
      version="2.0.0" \
      description="Elite MP4 to MP3 Conversion Bot"

# Entry point is handled by docker-compose or specific command
CMD ["python", "app/main.py"]
