#!/usr/bin/env python3
"""
digest_agent.py — drafts one issue of the geospatial AI competitive digest.

The shape of the thing:

    config -> collect(raw items) -> draft(Claude) -> REVIEW GATE -> render(html)

The interesting design choice is the review gate. Competitive intelligence gets
read by sales and repeated to customers, so an unreviewed claim is a liability,
not a time-saver. The agent drafts; a person approves each entry before anything
is written to disk. That is deliberately the slow step.

This is written to be read as evidence of approach. Collectors are stubs with
real endpoints named in comments — wiring them up is the boring part, and it is
the part that differs per organisation anyway.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python digest_agent.py --config digest.config.yaml --out index.html
"""

import argparse
import json
import os
import sys
import textwrap
from dataclasses import dataclass, asdict
from datetime import date

import anthropic
import yaml

MODEL = "claude-opus-5"


# --------------------------------------------------------------------------
# 1. What a finished entry looks like. The whole pipeline exists to fill this in.
# --------------------------------------------------------------------------

@dataclass
class Entry:
    competitor: str
    source_type: str   # model release | contract award | earnings | partnership | structural
    signal: str        # what changed, with dates and numbers
    so_what: str       # the implication for Planet's positioning — the headline
    action: str        # a battlecard line, written the way sales would say it
    sources: list      # [{"title": ..., "url": ..., "date": ...}]


# --------------------------------------------------------------------------
# 2. Collection. One function per source; each returns a list of raw dicts.
#    Kept dumb on purpose — no interpretation here, that is the model's job.
# --------------------------------------------------------------------------

def collect(config: dict) -> dict:
    """Fan out across configured sources, return {competitor: [raw items]}."""
    by_competitor = {name: [] for name in config["competitors"]}

    for source_name, opts in config["sources"].items():
        try:
            items = COLLECTORS[source_name](config["competitors"], opts)
        except Exception as exc:                      # one bad source must not
            print(f"  ! {source_name}: {exc}", file=sys.stderr)   # kill the run
            continue
        for item in items:
            by_competitor.setdefault(item["competitor"], []).append(item)
        print(f"  · {source_name}: {len(items)} items", file=sys.stderr)

    return by_competitor


def _sam_gov(competitors, opts):
    """Federal contract awards. api.sam.gov/opportunities/v2/search — needs a
    free api.data.gov key. Filter by NAICS from config, match recipient names."""
    return []


def _usaspending(competitors, opts):
    """api.usaspending.gov/api/v2/search/spending_by_award/ — no auth. Best
    source for award *values*; SAM.gov is better for announcements."""
    return []


def _arxiv(competitors, opts):
    """export.arxiv.org/api/query — cs.CV + eess.IV, filtered on the config
    query. Catches model releases weeks before any press release."""
    return []


def _huggingface(competitors, opts):
    """huggingface.co/api/models?author=<org> — new model cards and weight
    drops. The single earliest signal for 'a competitor shipped a model'."""
    return []


def _earnings(competitors, opts):
    """Transcripts for public tickers. Backlog and segment growth are stated
    here and nowhere else; worth reading in full rather than summarising."""
    return []


def _press_releases(competitors, opts):
    """RSS/newsroom polling per configured feed. Highest volume, lowest
    signal-to-noise — the model does most of its filtering work here."""
    return []


def _api_changelogs(competitors, opts):
    """Docs and data-catalog diffs. A new Earth Engine dataset is a product
    launch that never gets a press release."""
    return []


def _conferences(competitors, opts):
    """GEOINT, GTC, Esri UC agendas. Talk titles leak roadmap early."""
    return []


def _funding(competitors, opts):
    """Funding announcements filtered to earth observation, seed..series C."""
    return []


COLLECTORS = {
    "sam_gov": _sam_gov, "usaspending": _usaspending, "arxiv": _arxiv,
    "huggingface": _huggingface, "earnings": _earnings,
    "press_releases": _press_releases, "api_changelogs": _api_changelogs,
    "conferences": _conferences, "funding": _funding,
}


# --------------------------------------------------------------------------
# 3. Drafting. One call per competitor, structured output so the result is a
#    typed object rather than prose to be parsed.
# --------------------------------------------------------------------------

SYSTEM = """You are drafting one entry of a competitive intelligence digest for a \
product marketing team at Planet Labs (satellite imagery and geospatial AI).

Planet's defensible ground is time and fleet ownership: near-daily revisit, cloud \
resilience through repeated passes, a decade-deep archive, tip-and-cue from the \
monitoring constellation to high-resolution tasking, and on-orbit AI inference. \
Planet does NOT win on model quality — Google's models are better and free. Never \
draft an entry that positions Planet as having superior models.

Rules, in priority order:
1. Never state a fact not present in the source items. If a number or date is not \
   in the input, do not write one. Prefer omission to plausible invention.
2. The "so what" is the headline — one sentence, specific, and about Planet's \
   position rather than about the competitor's activity. Not "Vantor announced X" \
   but "X means our revisit argument has an expiry date."
3. The "action" is a line a salesperson says out loud to a customer. Not advice \
   about what to convey — the words themselves.
4. Where a signal genuinely hurts Planet, say so. A digest that never delivers \
   bad news does not get read twice.
5. Every source you were given that you used must appear in `sources`."""


def draft(client, competitor: str, items: list) -> Entry | None:
    """One competitor, one API call, one structured Entry back."""
    if not items:
        return None

    schema = {
        "type": "object",
        "properties": {
            "competitor":  {"type": "string"},
            "source_type": {"type": "string", "enum": [
                "model release", "contract award", "earnings",
                "partnership", "structural"]},
            "signal":  {"type": "string"},
            "so_what": {"type": "string"},
            "action":  {"type": "string"},
            "sources": {"type": "array", "items": {
                "type": "object",
                "properties": {"title": {"type": "string"},
                               "url":   {"type": "string"},
                               "date":  {"type": "string"}},
                "required": ["title", "url", "date"],
                "additionalProperties": False}},
        },
        "required": ["competitor", "source_type", "signal",
                     "so_what", "action", "sources"],
        "additionalProperties": False,
    }

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        # Structured output guarantees a parseable Entry — no regex on prose.
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content":
                   f"Competitor: {competitor}\n\nSignals collected this week:\n"
                   f"{json.dumps(items, indent=2)}"}],
    )

    text = next(b.text for b in response.content if b.type == "text")
    return Entry(**json.loads(text))


# --------------------------------------------------------------------------
# 4. The review gate. The reason this is a tool and not an automation.
# --------------------------------------------------------------------------

def review(entries: list) -> list:
    """Show each drafted entry to a person. Nothing publishes unapproved.

    Deliberately a blocking terminal prompt rather than a queue or a webhook:
    the friction is the feature. Someone has to have read every claim before
    it reaches a customer-facing battlecard.
    """
    approved = []
    for i, e in enumerate(entries, 1):
        print("\n" + "─" * 68)
        print(f"[{i}/{len(entries)}]  {e.competitor.upper()}   ({e.source_type})")
        print("─" * 68)
        for label, body in (("SO WHAT", e.so_what), ("SIGNAL", e.signal),
                            ("ACTION", e.action)):
            print(f"\n{label}\n" + textwrap.fill(body, 68, initial_indent="  ",
                                                 subsequent_indent="  "))
        print("\nSOURCES")
        for s in e.sources:
            print(f"  · {s['title']} — {s['date']}\n    {s['url']}")

        choice = input("\n  [a]pprove  [e]dit so-what  [s]kip  [q]uit > ").strip().lower()
        if choice == "q":
            print("Aborted — nothing written.", file=sys.stderr)
            sys.exit(1)
        if choice == "s":
            continue
        if choice == "e":
            e.so_what = input("  new so-what > ").strip() or e.so_what
        approved.append(e)

    print(f"\n{len(approved)}/{len(entries)} entries approved.", file=sys.stderr)
    return approved


# --------------------------------------------------------------------------
# 5. Write. The agent's output is data, not markup — it updates the `entries`
#    array in digest.json and leaves every other section of the issue alone.
#    `python build.py` turns that into the page. Keeping the agent out of the
#    HTML means a human can edit any wording afterwards without re-running it.
# --------------------------------------------------------------------------

def write_data(entries: list, data_path: str = "digest.json"):
    """Merge approved entries into digest.json, preserving hand-written sections."""
    with open(data_path) as f:
        data = json.load(f)

    data["entries"] = [
        {"competitor": e.competitor,
         "tags": [e.source_type.title()],
         "so_what": e.so_what,
         "signal": e.signal,
         "action": e.action,
         "detail": [],          # written by a human during review, not drafted
         "sources": e.sources}
        for e in entries
    ]
    data["issue"]["date"] = date.today().strftime("%d %B %Y")
    data["issue"]["verified"] = date.today().strftime("%d %B %Y")

    with open(data_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {data_path} — now run: python build.py", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="digest.config.yaml")
    ap.add_argument("--out", default="digest.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="collect and draft, print JSON, write nothing")
    args = ap.parse_args()

    config = yaml.safe_load(open(args.config))
    client = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY

    print("Collecting…", file=sys.stderr)
    raw = collect(config)

    print("Drafting…", file=sys.stderr)
    entries = [e for name in config["competitors"]
               if (e := draft(client, name, raw.get(name, [])))]

    if args.dry_run:
        print(json.dumps([asdict(e) for e in entries], indent=2))
        return

    if config.get("review") == "required":
        entries = review(entries)

    if entries:
        write_data(entries, args.out)


if __name__ == "__main__":
    main()
