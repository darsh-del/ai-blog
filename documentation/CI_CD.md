# CI/CD Pipeline

`.github/workflows/ci-cd.yml` — three jobs, each gated on the previous:

```
test  --->  build-push  --->  deploy
(all      (push to main   (push to main
 branches, only, after       only, after
 PRs too)  tests pass)       image is pushed)
```

## test (every push + PR)
Runs on a plain `ubuntu-latest` runner — no Docker, no Chromium. The test
suite (`tests/test_suite.py`) mocks every external client (LLM, GenAI,
SMTP — see `tests/conftest.py`), so it never needs real API keys or a
browser. Also runs `pylint` and `pip-audit`, both **informational** (`||
true` / `--exit-zero`): they annotate the run but don't fail it, since the
repo has pre-existing lint debt this pipeline didn't introduce. Flip that
if you want them to gate merges once the debt's paid down.

## build-push (push to `main` only)
Builds the same `Dockerfile` this repo already had, once, and pushes it to
GitHub Container Registry as:
- `ghcr.io/darsh-del/ai-blog:latest`
- `ghcr.io/darsh-del/ai-blog:sha-<12-char-commit-sha>` (what actually gets deployed and what rollback targets)

Trivy scans both the filesystem and the built image for CRITICAL/HIGH CVEs
(informational — same reasoning as lint). Build layers are cached via the
GitHub Actions cache so repeat builds (the `torch`/`sentence-transformers`
install in particular) aren't a full reinstall every time.

## deploy (push to `main` only, after build-push)
SSHes into the EC2 box and:
1. Logs into `ghcr.io` with the run's own short-lived `GITHUB_TOKEN` — no
   long-lived registry credential is ever stored on the server.
2. Writes the new image tag into `.env`'s `IMAGE_TAG=` line (the **only**
   line in `.env` this pipeline ever touches — everything else in that file
   is your app config and secrets, untouched, never uploaded anywhere).
3. `docker compose pull && up -d --no-build` — pulls the pre-built image,
   never rebuilds on the EC2 box itself.
4. Smoke-tests it: container must still be `Running` 15s later, and the
   cron entry `setup_cron.py` registers on container start must actually be
   present (`crontab -l` inside the container).
5. **If the smoke test fails, it automatically rewrites `IMAGE_TAG` back to
   the previous value, restarts, and fails the workflow run** — so a bad
   deploy self-heals instead of leaving the box on a broken image.

Gated behind a GitHub **Environment** named `production` — configure a
required reviewer there (Settings → Environments → production) if you want
a manual approval click before every deploy; leave it unconfigured for
fully automatic deploys on merge.

Runs are serialized (`concurrency: production-deploy`) so two pushes in
quick succession can't race each other's `docker compose up`.

### Manual redeploy
`Actions → CI/CD → Run workflow`, tick "Skip build, just redeploy the
currently published :latest image" — reruns the deploy job only, no new
image built. Useful after changing `.env` on the server or if you just
want to force a restart.

## One-time setup

### 1. EC2 host
Run once on a fresh instance: [`deploy/bootstrap_ec2.sh`](../deploy/bootstrap_ec2.sh).
Installs Docker, clones the repo, seeds `.env` from `example.env` if
missing, and does the first `docker compose up`. **You still have to fill
in real secrets in `.env` yourself** — the pipeline never writes anything
into it except `IMAGE_TAG`.

### 2. GitHub repo secrets (Settings → Secrets and variables → Actions)
| Secret | Value |
|---|---|
| `EC2_HOST` | Public IP or DNS of the EC2 instance |
| `EC2_USERNAME` | SSH user (e.g. `ubuntu`) |
| `EC2_SSH_KEY` | Private half of a keypair whose public half is in that user's `~/.ssh/authorized_keys` |
| `EC2_SSH_PORT` | Optional, defaults to `22` |
| `EC2_DEPLOY_DIR` | Absolute path to the cloned repo on the box, e.g. `/home/ubuntu/ai-blog` |

`GITHUB_TOKEN` (GHCR auth) is automatic — no secret to create.

### 3. GHCR package visibility
If the repo is private, the `ghcr.io/darsh-del/ai-blog` package is private
too by default. The workflow's own `GITHUB_TOKEN` can always push/pull it.
For the EC2 box's own pulls to work outside a workflow run (e.g. the
bootstrap script's first pull, or a manual `docker compose pull` you run by
hand later), either make the package public (Package settings → Change
visibility) or `docker login ghcr.io` on the box once with a PAT that has
`read:packages`.

## Why not X

- **Self-hosted GitHub Actions runner on the EC2 box** — skipped. It would
  remove the SSH step, but self-hosted runners accumulate state (stale
  `known_hosts`, leftover processes) between runs and GitHub explicitly
  warns against them outside a controlled, single-purpose box. This is a
  single cron container; SSH from a clean GitHub-hosted runner every time
  is simpler and doesn't leave residue.
- **Blue-green / zero-downtime deploy** — skipped. There's no live HTTP
  traffic to protect yet (the container currently just runs a cron job —
  `api/main.py` doesn't exist in this repo yet, see the `TODO`s in
  `Dockerfile`). A `docker compose up -d` restart's few seconds of downtime
  cost nothing here. Revisit once the FastAPI server is real and serving
  requests.
- **CodeQL** — skipped for now; `pip-audit` + Trivy already cover the
  dependency-CVE surface for a small internal tool. Add
  `github/codeql-action` if/when this gets more external contributors.
