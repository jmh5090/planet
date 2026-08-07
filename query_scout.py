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
# 2. Analyze. One batched Claude call for the whole list, structured JSON back.
#    This is the judgment: two hard filters drop anything that fails, and three
#    scores rank what survives. The system prompt is where that judgment lives.
# --------------------------------------------------------------------------

SYSTEM = """You are a content strategist for Planet Labs' Queryable Earth — an \
agentic AI that answers natural-language questions from a decade of near-daily \
global satellite imagery.

You are given a batch of recent news stories. For each story, decide whether it \
could become a compelling "post candidate": a story where a person who has never \
touched GIS software would ask a question that Queryable Earth can answer from \
orbit, and the answer would make a shareable LinkedIn post. A human will later \
type the top prompts into the beta by hand.

Apply TWO HARD FILTERS first. Drop any story that fails either one — do not \
soften a borderline story to keep it; when in doubt, drop it.

1. SATELLITE-VISIBILITY. Keep only changes physically observable from orbit at \
   roughly 3-metre resolution over days-to-years: construction and industrial \
   buildout, deforestation, water and reservoir levels, flooding, burn scars, \
   ports and shipping, mining, solar/energy buildout, crop change, storage-tank \
   levels, and the like. REJECT anything whose substance is policy, prices, \
   earnings, court rulings, sentiment, indoor or personal activity, or detail \
   finer than a few metres.

2. SAFE-LANE. REJECT active-conflict, military, troop-movement, and \
   OSINT-sensitive topics. Planet has defense customers and freelancing on these \
   publicly is off-limits. Favour economic, environmental, civic, and commercial \
   stories.

Then SCORE every surviving story from 1 to 10 on each axis:

- longitudinal_moat — how much the answer DEPENDS on frequent, longitudinal \
  imagery rather than a single snapshot. THIS IS THE PRIMARY RANKING KEY. \
  Planet's moat is a decade of near-daily global imagery; a competitor can also \
  run a single natural-language query against one image, so a story answerable \
  from ONE image must score LOW. Reward rate-of-change, recovery trajectories, \
  and progression over time.
- virality — how shareable the resulting post would be on LinkedIn.
- confidence — how confident you are that the beta can actually answer the \
  prompt from imagery.

Return ONLY a JSON array — no prose, no markdown, no code fences. Each element \
is one surviving story with exactly these fields:

  headline               (carry through from the story's title)
  source                 (carry through from the story)
  url                    (carry through from the story)
  visibility_reason      (one sentence: what is observable from orbit and why)
  persona                (the new, non-GIS buyer who would care)
  why_they_care          (one sentence, in the persona's terms)
  business_question      (the question in the persona's own words)
  queryable_earth_prompt (a natural-language prompt, ready to paste into the beta)
  linkedin_hook          (<= 140 characters)
  longitudinal_moat      (integer 1-10)
  virality               (integer 1-10)
  confidence             (integer 1-10)

If no story survives the filters, return an empty array: []"""


def _extract_json(text: str) -> list[dict]:
    """Pull the JSON array out of the model's reply, tolerating stray prose or
    code fences. We prompt for a bare array but never trust that we got one."""
    text = text.strip()
    if text.startswith("```"):
        # Strip a leading ```json / ``` fence and the trailing fence.
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON array found in model response")
    return json.loads(text[start:end + 1])


def analyze(client, items: list[dict], config: dict) -> list[dict]:
    """One batched call. Returns the passing candidates (unranked)."""
    if not items:
        return []

    model = config.get("model", MODEL)
    response = client.messages.create(
        model=model,
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content":
                   "Recent news stories:\n" + json.dumps(items, indent=2, ensure_ascii=False)}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return _extract_json(text)


# --------------------------------------------------------------------------
# 3. Rank. longitudinal_moat first — that is Planet's moat — then virality plus
#    confidence as the tie-break.
# --------------------------------------------------------------------------

def _score(candidate: dict, key: str) -> int:
    try:
        return int(candidate.get(key, 0))
    except (TypeError, ValueError):
        return 0


def rank(candidates: list[dict]) -> list[dict]:
    return sorted(
        candidates,
        key=lambda c: (_score(c, "longitudinal_moat"),
                       _score(c, "virality") + _score(c, "confidence")),
        reverse=True,
    )


# --------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------

def pipeline(config: dict) -> list[dict]:
    """The real pipeline the live demo runs: ingest -> analyze -> rank."""
    try:
        import anthropic
    except ImportError:
        print("anthropic is required: pip install anthropic", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    print("Ingesting…", file=sys.stderr)
    items = ingest(config)
    print(f"{len(items)} items after de-dupe.", file=sys.stderr)

    print("Analyzing…", file=sys.stderr)
    client = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY
    candidates = rank(analyze(client, items, config))
    print(f"{len(candidates)} candidates passed the filters.", file=sys.stderr)
    return candidates


def cmd_run(args, config: dict):
    candidates = pipeline(config)

    if args.dry_run:
        print(json.dumps(candidates, indent=2, ensure_ascii=False))
        return

    # Delivery is wired in the next stage.
    print("Analysis complete. Delivery not yet wired up — "
          "use --dry-run to inspect ranked candidates.", file=sys.stderr)


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
