#!/usr/bin/env bash
# Double-click this in Finder to run query-scout and open the report in your
# browser. Nothing to type.
#
# One-time setup before the first double-click:
#   1. cp .env.example .env, then put your ANTHROPIC_API_KEY in .env
#   2. Right-click this file > Open (not double-click) the very first time —
#      macOS Gatekeeper blocks a first double-click on an unsigned local
#      script and needs that one explicit "Open" to trust it going forward.
cd "$(dirname "$0")" || exit 1

echo "Running query-scout…"
echo

if ./run.sh --notify html "$@"; then
    echo
    echo "Done — opening the report…"
    open "out/latest.html"
else
    echo
    echo "query-scout hit an error (see above) — the report was not updated."
fi

echo
read -n 1 -s -r -p "Press any key to close this window..."
echo
