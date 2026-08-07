#!/usr/bin/env bash
# One-command wrapper for the live demo. Runs the full pipeline and delivers
# through the configured channel (html by default). Pass through any flags:
#   ./run.sh                    # deliver to the default channel
#   ./run.sh --notify console   # print the digest to the terminal
#   ./run.sh --dry-run          # ingest + analyze, print JSON, deliver nothing
#
# Meant for both on-demand use and a weekly cron / Task Scheduler entry:
#   0 6 * * 1  /path/to/planet/run.sh
set -euo pipefail
cd "$(dirname "$0")"

# Pick up ANTHROPIC_API_KEY (and any notifier credentials) from .env if present,
# so a double-clicked launcher works without exporting anything in a shell
# first — Finder starts a fresh shell that doesn't see earlier `export`s.
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

exec python3 query_scout.py run "$@"
