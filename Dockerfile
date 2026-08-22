# syntax=docker/dockerfile:1

# Stage 1: Build stage
FROM python:3.14-slim-bookworm AS builder

# Set build-time optimization variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Setup virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .

# OPTIMIZATION: Install CPU-only Torch first to save ~1.5GB of GPU binaries
# This is critical because sentence-transformers pulls in the full heavy torch by default.
RUN pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.14-slim-bookworm AS runtime

# Set runtime environment variables (Keeping all original project configs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PATH="/opt/venv/bin:$PATH" \
    CHROME_BIN=/usr/bin/chromium \
    CHROMIUM_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    USE_PLAIN_SELENIUM=1 \
    APP_DATA_DIR=/app/data \
    REDIS_HOST=localhost \
    REDIS_PORT=6379

WORKDIR /app

# Install runtime dependencies (Chromium, curl, and cron for the scheduled
# generate_and_email.py run — see entrypoint.sh / setup_cron.py)
# In Bookworm, chromium automatically pulls in necessary libnss3, libgbm1, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    curl \
    fonts-liberation \
    cron \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy pre-compiled virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# --- Layer Ordering ---
# Copy project structure
COPY prompts ./prompts
COPY utils ./utils
COPY src ./src
# TODO: no api/ package exists anywhere in this repo yet (pre-existing gap,
# unrelated to the cron work below) — uncomment once api/main.py is added.
# COPY api ./api
# Root-level entry point scripts run by the cron job (see entrypoint.sh)
COPY generate_and_email.py setup_cron.py ./
# Copy only configurations from data to avoid baking in existing local databases
COPY data/config ./data/config

# Pre-create all original data directories with proper structure
RUN mkdir -p /app/data/database /app/data/output /app/data/output/brand \
    /app/data/output/json /app/data/output/images /app/data/output/logs \
    /app/data/metadata /app/data/vector_store

COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 8000

# TODO: re-enable once api/main.py exists — see the COPY api ./api TODO above.
# HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
#     CMD curl -f http://localhost:8000/health || exit 1

# entrypoint.sh snapshots the container's env for cron, registers the
# generate_and_email.py cron job from GENERATE_EMAIL_CRON_SCHEDULE, starts
# the cron daemon, then execs the command below as the container's main process.
ENTRYPOINT ["./entrypoint.sh"]

# TODO: swap back to the FastAPI server once api/main.py exists:
#   CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
# Placeholder keeps the container alive (foreground process for ENTRYPOINT's `exec "$@"`)
# so the cron daemon started by entrypoint.sh has something to run alongside.
CMD ["tail", "-f", "/dev/null"]
