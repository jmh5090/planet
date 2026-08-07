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
exec python3 query_scout.py run "$@"
