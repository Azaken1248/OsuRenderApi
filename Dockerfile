FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    python3-dev \
    wget \
    unzip \
    ffmpeg \
    xvfb \
    libnss3 \
    libgl1 \
    libgl1-mesa-dri \
    libgbm1 \
    libgtk-3-0 \
    libasound2 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libxrandr2 \
    libxcursor1 \
    libxinerama1 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download and install danser for local rendering (if USE_MODAL_GPU=0)
RUN wget https://github.com/Wieku/danser-go/releases/download/0.11.0/danser-0.11.0-linux.zip && \
    unzip danser-0.11.0-linux.zip -d /usr/local/bin/danser && \
    chmod +x /usr/local/bin/danser/danser-cli && \
    rm danser-0.11.0-linux.zip

ENV DANSER_BIN=/usr/local/bin/danser/danser-cli
ENV PYTHONPATH=/app

# Copy application source
COPY . .

# Expose FastAPI port
EXPOSE 8727

# Entrypoint script will handle migrations and starting the server
CMD ["bash", "scripts/start.sh"]
