#!/bin/sh
# One-time EC2 host setup. Run ONCE, manually, on a fresh instance before the
# first CI/CD deploy ever runs (the GitHub Actions workflow only pulls images
# and restarts the stack — it never installs Docker or clones the repo).
#
# Usage (on the EC2 box, as a sudo-capable user):
#   curl -fsSL https://raw.githubusercontent.com/darsh-del/ai-blog/main/deploy/bootstrap_ec2.sh | sh
# or copy it up and run: sh bootstrap_ec2.sh
set -e

DEPLOY_DIR="${DEPLOY_DIR:-$HOME/ai-blog}"
REPO_URL="${REPO_URL:-https://github.com/darsh-del/ai-blog.git}"

echo "==> Installing Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  echo "    Docker installed. Log out/in (or run 'newgrp docker') for group membership to apply."
else
  echo "    Docker already installed, skipping."
fi

echo "==> Cloning repo to $DEPLOY_DIR"
if [ ! -d "$DEPLOY_DIR/.git" ]; then
  git clone "$REPO_URL" "$DEPLOY_DIR"
else
  echo "    Already cloned, skipping."
fi

cd "$DEPLOY_DIR"

if [ ! -f .env ]; then
  echo "==> No .env found — copying example.env as a starting point"
  cp example.env .env
  echo "    !!! Edit $DEPLOY_DIR/.env now and fill in real API keys/credentials"
  echo "    !!! before the cron job's first scheduled run."
fi

# CI/CD only ever rewrites the IMAGE_TAG line in .env (see .github/workflows/ci-cd.yml).
grep -q '^IMAGE_TAG=' .env || echo "IMAGE_TAG=latest" >> .env

mkdir -p src/credentials tokens

echo "==> Pulling the current published image and starting the stack"
docker login ghcr.io -u "$GHCR_USER" 2>/dev/null || {
  echo "    Skipping 'docker login' — set GHCR_USER and pipe a token via stdin if the";
  echo "    ghcr.io/darsh-del/ai-blog package is private, then re-run:";
  echo "      echo \$GHCR_TOKEN | docker login ghcr.io -u <user> --password-stdin";
}
docker compose pull blog-generator || echo "    (no image published yet — that's fine before the first CI run)"
docker compose up -d --no-build --remove-orphans

echo ""
echo "==> Done. Next steps:"
echo "    1. Fill in $DEPLOY_DIR/.env with real secrets if you haven't."
echo "    2. In the GitHub repo Settings -> Secrets, set: EC2_HOST, EC2_USERNAME,"
echo "       EC2_SSH_KEY (the private half of a key whose public half is in"
echo "       ~/.ssh/authorized_keys here), EC2_SSH_PORT (optional), and"
echo "       EC2_DEPLOY_DIR=$DEPLOY_DIR."
echo "    3. Push to main — the ci-cd.yml workflow takes it from here."
