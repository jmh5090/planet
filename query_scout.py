#!/usr/bin/env python3
"""
query_scout.py — proposes ranked "post candidates" for Planet's Queryable Earth.

Stage one of a data-storytelling pipeline. The tool reads recent news and, for
each story that survives two hard filters, proposes: who the dormant non-GIS
buyer is, the question they'd ask, and the exact natural-language prompt to type
into the Queryable Earth beta. A human runs the top prompts in the beta manually.
This tool never touches the beta.

The shape of the thing:

    config -> ingest(raw news) -> analyze(Claude) -> rank -> deliver(notifier)

Ingest is pluggable: the default source is RSS via feedparser, but everything
downstream consumes a plain list of {title, source, url, summary} dicts, so
swapping in NewsAPI or GDELT is one new function in the SOURCES registry.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python query_scout.py run                 # full pipeline, then deliver
    python query_scout.py run --dry-run       # ingest + analyze, print JSON, deliver nothing
    python query_scout.py run --notify slack  # override the configured channel
"""

import argparse
import json
import os
import sys

CONFIG_PATH = "queryscout.config.json"
MODEL = "claude-sonnet-4-6"


# --------------------------------------------------------------------------
# 0. Config. Feeds live here, not in code — pointing the tool at a different
#    source set is a config edit, not a code change.
# --------------------------------------------------------------------------

def load_config(path: str = CONFIG_PATH) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Config is not valid JSON ({path}): {exc}", file=sys.stderr)
        sys.exit(1)


# --------------------------------------------------------------------------
# 1. Ingest. One function per source; each returns a list of raw dicts with a
#    stable shape — {title, source, url, summary}. No interpretation here, that
#    is the model's job. Adding NewsAPI or GDELT means adding one function to
#    SOURCES and naming it in the config; nothing downstream changes.
# --------------------------------------------------------------------------

def _rss(config: dict) -> list[dict]:
    """Poll the RSS feeds named in config. Default source."""
    try:
        import feedparser
    except ImportError:
        print("feedparser is required for the RSS source: pip install feedparser",
              file=sys.stderr)
        sys.exit(1)

    items: list[dict] = []
    for url in config.get("feeds", []):
        parsed = feedparser.parse(url)
        source = parsed.feed.get("title", url)
        if parsed.bozo and not parsed.entries:
            print(f"  ! {url}: {parsed.bozo_exception}", file=sys.stderr)
            continue
        for entry in parsed.entries:
            items.append({
                "title": entry.get("title", "").strip(),
                "source": source,
                "url": entry.get("link", ""),
                # feedparser exposes the blurb as .summary; some feeds omit it.
                "summary": entry.get("summary", "").strip(),
            })
        print(f"  · {source}: {len(parsed.entries)} items", file=sys.stderr)
    return items


def _newsapi(config: dict) -> list[dict]:
    """Placeholder — newsapi.org/v2/everything. Would read an API key and query
    from config and return the same {title, source, url, summary} shape. Wiring
    it up is the only change needed to swap sources."""
    raise NotImplementedError("newsapi source not wired up — see docstring")


def _gdelt(config: dict) -> list[dict]:
    """Placeholder — api.gdeltproject.org/api/v2/doc/doc. Same output contract as
    _rss; GDELT's DOC API needs no key and is good for global event coverage."""
    raise NotImplementedError("gdelt source not wired up — see docstring")


SOURCES = {"rss": _rss, "newsapi": _newsapi, "gdelt": _gdelt}


def ingest(config: dict) -> list[dict]:
    """Fan out to the configured source, de-dupe by URL, cap at max_items."""
    source_name = config.get("source", "rss")
    if source_name not in SOURCES:
        print(f"Unknown source '{source_name}'. Options: {', '.join(SOURCES)}",
              file=sys.stderr)
        sys.exit(1)

    raw = SOURCES[source_name](config)

    seen, items = set(), []
    for item in raw:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(item)

    max_items = config.get("max_items", 40)
    return items[:max_items]


# --------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------

def cmd_run(args, config: dict):
    print("Ingesting…", file=sys.stderr)
    items = ingest(config)
    print(f"{len(items)} items after de-dupe.", file=sys.stderr)

    if args.dry_run:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return

    # Analysis and delivery are wired in later stages.
    print("Ingest complete. Analysis and delivery not yet wired up — "
          "use --dry-run to inspect ingested items.", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(prog="query-scout",
                                 description="Propose ranked Queryable Earth post candidates from the news.")
    ap.add_argument("--config", default=CONFIG_PATH, help="path to config JSON")
    sub = ap.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the pipeline now (on-demand or via cron)")
    run.add_argument("--dry-run", action="store_true",
                     help="ingest and analyze, print JSON, deliver nothing")
    run.add_argument("--notify", choices=["html", "email", "slack", "console"],
                     help="delivery channel (default from config, or html)")
    run.add_argument("--json", metavar="FILE",
                     help="also write the ranked candidates to FILE as JSON")

    args = ap.parse_args()
    config = load_config(args.config)

    if args.command == "run":
        cmd_run(args, config)


if __name__ == "__main__":
    main()
