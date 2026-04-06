FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (FFmpeg + Deno)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && curl -fsSL https://deno.land/x/install/install.sh | sh \
    && mv /root/.deno/bin/deno /usr/local/bin/ \
    && apt-get purge -y curl unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure temp directory exists
RUN mkdir -p temp_uploads

# Start the unified bot
CMD ["python", "main.py"]
