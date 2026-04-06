FROM python:3.11-slim

WORKDIR /app

# Install FFmpeg and basic utils
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Deno for yt-dlp signatures
RUN curl -fsSL https://deno.land/x/install/install.sh | sh \
    && mv /root/.deno/bin/deno /usr/local/bin/

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Shared temp directory
RUN mkdir -p temp_uploads

CMD ["python", "bot.py"]
