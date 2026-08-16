"""
setup_cron.py
==============
Installs (or removes) the standard POSIX crontab entry that runs
generate_and_email.py on a schedule. Uses only `crontab -l` / `crontab -`,
which behave identically on macOS and any Linux server — nothing here is
OS-specific. The schedule itself lives in .env (GENERATE_EMAIL_CRON_SCHEDULE)
so changing "when" never requires touching code or re-editing crontab by hand —
just update the .env value and re-run this script on whichever machine runs it.

Usage:
    python3 setup_cron.py            # install/update the cron entry from .env
    python3 setup_cron.py --remove   # remove the cron entry, leave other jobs untouched
    python3 setup_cron.py --show     # print the entry that would be installed, without touching crontab

This script only ever touches ONE line in the crontab — the one tagged with
CRON_MARKER below — so any other cron jobs already on the system are left
exactly as they were.

Docker note: a container has no cron daemon running by default. `crontab -l/-`
only edits the crontab *file* — something still has to run `cron`/`crond` as a
background process for it to ever fire. If/when this moves into the project's
Dockerfile, install a cron package (e.g. `apt-get install -y cron`) and start
the daemon from the container's entrypoint alongside the app process; this
script can then be run once (e.g. in that same entrypoint) to register the job.
"""
import os
import platform
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.resolve()
LOG_DIR = PROJECT_ROOT / "data" / "output" / "logs"
LOG_FILE = LOG_DIR / "cron_generate_and_email.log"
CRON_MARKER = "# ai-blog-generator:generate_and_email"


def _build_cron_line() -> str:
    """Read the schedule from .env and build the full crontab line."""
    load_dotenv(PROJECT_ROOT / ".env")
    schedule = os.getenv("GENERATE_EMAIL_CRON_SCHEDULE", "30 10 * * *").strip()

    # Cheap sanity check only — cron itself is the real validator when we install.
    # A 5-field cron expression is "minute hour day month weekday".
    if len(schedule.split()) != 5:
        print(
            f"[ERROR] GENERATE_EMAIL_CRON_SCHEDULE='{schedule}' is not a valid 5-field cron "
            "expression (minute hour day month weekday), e.g. '30 10 * * *' for 10:30 daily."
        )
        sys.exit(1)

    command = f"cd {PROJECT_ROOT} && {sys.executable} generate_and_email.py >> {LOG_FILE} 2>&1"
    return f"{schedule} {command} {CRON_MARKER}"


def _run_crontab(args: list, **kwargs) -> subprocess.CompletedProcess:
    """Run the `crontab` binary, failing with actionable per-OS guidance if it's missing."""
    try:
        return subprocess.run(["crontab", *args], capture_output=True, text=True, check=False, **kwargs)
    except FileNotFoundError:
        if platform.system() == "Linux":
            hint = "install it first, e.g. `apt-get install -y cron` (Debian/Ubuntu) or `apk add dcron` (Alpine)."
        else:
            hint = "install a cron package for this OS."
        print(f"[ERROR] `crontab` command not found on this system — {hint}")
        sys.exit(1)


def _read_existing_crontab() -> list:
    """Return the current crontab as a list of lines (empty list if none exists yet)."""
    result = _run_crontab(["-l"])
    if result.returncode != 0:
        # "no crontab for <user>" is expected on a machine that never had one — not an error.
        return []
    return result.stdout.splitlines()


def _write_crontab(lines: list) -> None:
    payload = "\n".join(lines) + ("\n" if lines else "")
    result = _run_crontab(["-"], input=payload)
    if result.returncode != 0:
        print(f"[ERROR] Failed to update crontab: {result.stderr}")
        sys.exit(1)


def install() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    new_line = _build_cron_line()

    existing = [line for line in _read_existing_crontab() if CRON_MARKER not in line]
    existing.append(new_line)
    _write_crontab(existing)

    print("[OK] Cron job installed/updated:")
    print(f"     {new_line}")
    print(f"[INFO] Runs will be logged to: {LOG_FILE}")
    print(f"[INFO] This entry runs on whatever machine you execute this script on: {platform.node() or 'this host'} "
          f"({platform.system()}). Re-run it on the actual target machine before relying on it.")

    system = platform.system()
    if system == "Darwin":
        print(
            "[IMPORTANT] macOS requires cron to be granted Full Disk Access, or scheduled runs fail "
            "silently:\n"
            "  System Settings -> Privacy & Security -> Full Disk Access -> add /usr/sbin/cron\n"
            "  Also confirm the project directory (if on removable/network storage) is mounted "
            "at the scheduled time."
        )
    elif system == "Linux":
        print(
            "[IMPORTANT] Make sure the cron daemon is actually running, or this entry will sit in the "
            "crontab and never fire:\n"
            "  systemctl status cron   (or: service cron status / crond status, depending on distro)\n"
            "  Inside a Docker container specifically: cron is NOT started automatically — see the "
            "Docker note at the top of this file."
        )


def remove() -> None:
    existing = _read_existing_crontab()
    remaining = [line for line in existing if CRON_MARKER not in line]
    if len(remaining) == len(existing):
        print("[INFO] No matching cron entry found — nothing to remove.")
        return
    _write_crontab(remaining)
    print("[OK] Cron job removed. All other crontab entries left untouched.")


if __name__ == "__main__":
    if "--remove" in sys.argv:
        remove()
    elif "--show" in sys.argv:
        print(_build_cron_line())
    else:
        install()
