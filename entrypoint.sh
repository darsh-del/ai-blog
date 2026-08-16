#!/bin/sh
# Container entrypoint: prepares the cron job, then hands off to the real
# command (CMD, e.g. uvicorn) as the container's foreground process.
set -e

# cron-spawned processes get a bare environment and never see the vars Docker
# injected into this container (via env_file/environment in docker-compose.yml)
# — snapshot them into a real .env file so load_dotenv() (already used by
# generate_and_email.py / setup_cron.py) picks them up no matter how the
# process was launched.
printenv | grep -Ev '^(HOME|HOSTNAME|PWD|SHLVL|_)=' > /app/.env

# Register/refresh this container's cron entry from GENERATE_EMAIL_CRON_SCHEDULE.
python setup_cron.py

# Start the cron daemon in the background (Debian's `cron` self-daemonizes;
# no -f, so this returns immediately and does not block the line below).
cron

exec "$@"
