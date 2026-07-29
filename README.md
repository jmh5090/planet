# Geospatial AI Competitive Digest

A weekly competitive intelligence digest for geospatial AI and defense — a market
where the standard AI competitive-intelligence stack (review-site scraping, ad
libraries, pricing-page diffing) returns an empty result set.

| File | What it is |
|---|---|
| **`digest.json`** | **Every word on the page.** The file you edit. |
| `template.html` | CSS and page chrome. Touch this only to change how it looks. |
| `build.py` | `digest.json` + `template.html` → `index.html`. No dependencies. |
| `index.html` | Generated. Deploy this. Self-contained, no JS, no backend. |
| `digest_agent.py` | Drafts next week's entries into `digest.json`. Human approval gate. |
| `digest.config.yaml` | Competitor list, signal sources, cadence. |
| `netlify.toml` | Publishes the repo root as-is, plus security headers. |

Content and presentation are separate on purpose: editing a battlecard line
shouldn't require opening HTML, and restyling the page shouldn't risk changing a
number. `index.html` is generated — edit `digest.json` and rebuild, or your
change gets overwritten on the next build.

---

## Editing it

Everything is in `digest.json` — masthead, the mismatch table, all five entries,
the trajectory section, the footer. Change a line, rebuild, redeploy:

```bash
python build.py          # digest.json + template.html -> index.html
python build.py --check  # exit 1 if index.html is stale (useful in CI)
```

Strings in `digest.json` are trusted HTML fragments, so inline `<b>` and `<em>`
work in any field. Source URLs are the exception — they're escaped and
scheme-checked at build time (`http`/`https` only), because those come from the
agent rather than from you.

**Every claim is linked.** Each entry carries a `sources` array of
`{title, url, date}`. A source with a `url` renders as a clickable link with an
↗ marker; a source without one renders in muted plain text, so an unverifiable
citation looks visibly different from a verifiable one. That distinction is the
point — 18 of 19 entry sources link out, and the one that doesn't is obvious.

---

## What the agent does

```
config → collect(raw items) → draft(Claude) → REVIEW GATE → digest.json → build.py → index.html
```

1. **Collect.** Queries the sources named in `digest.config.yaml` — SAM.gov and
   USASpending for contract awards, arXiv and Hugging Face for model releases,
   earnings transcripts, newsroom feeds, API changelogs, conference agendas,
   funding announcements.
2. **Draft.** One Claude call per competitor, using structured outputs so each
   entry comes back as a typed object rather than prose to be parsed. Each entry
   is `signal` (what changed) → `so what` (implication for Planet's positioning)
   → `action` (a battlecard line, written the way sales would say it).
3. **Review.** Every entry is printed to the terminal for approval, edit, or
   skip. Nothing publishes unreviewed. This is the slow step on purpose —
   competitive claims get repeated to customers, so an unreviewed number is a
   liability, not a time saving.
4. **Write.** Approved entries are merged into the `entries` array of
   `digest.json`, leaving every hand-written section of the issue untouched. The
   agent never writes HTML — `build.py` does that, so you can edit any wording
   afterwards without re-running the model.

The system prompt carries Planet's actual position — that the defensible ground
is time and fleet ownership, and that Planet does *not* win on model quality. It
is explicitly instructed to surface signals that hurt Planet. A digest that only
delivers good news doesn't get read twice.

---

## Running it

```bash
pip install anthropic pyyaml     # build.py itself needs neither
export ANTHROPIC_API_KEY=sk-ant-...

python digest_agent.py --dry-run   # collect + draft, print JSON, write nothing
python digest_agent.py             # full run with the review gate -> digest.json
python build.py                    # digest.json -> index.html
```

The collectors in `digest_agent.py` are stubs with the real endpoints named in
their docstrings. Wiring them up is the boring part and it's organisation-specific
— API keys, rate limits, whatever entity-matching your competitor names need.
Budget most of your setup time there.

---

## Cost

Priced against `claude-opus-5` at $5 / $25 per million tokens (input / output).

| | |
|---|---|
| Per competitor | ~25K input, ~1K output ≈ **$0.15** |
| Per issue (5 competitors) | ≈ **$0.75** |
| Per month (weekly cadence) | ≈ **$3** |
| With redrafts and iteration | **$5–10/month** realistically |

Rounding up generously it's under $15/month. The API cost is not the constraint
on this system — the human review time is, at roughly 15 minutes per issue.

Swapping `MODEL` to `claude-sonnet-5` cuts the model cost roughly in half. I'd
keep Opus: the judgment call this makes — "is this signal actually material to
positioning, or just news?" — is exactly the kind of thing worth paying for, and
$3/month is not where you optimise.

---

## Setup time

| | |
|---|---|
| Clone, install, first `--dry-run` against stub collectors | **~15 minutes** |
| Wiring two or three real collectors (SAM.gov, arXiv, RSS) | **half a day** |
| Tuning the system prompt to your team's voice | **an hour, then ongoing** |
| Full source set with entity matching and dedupe | **2–3 days** |

Start with three sources, not nine. The digest is useful at three.

---

## Pointing it at a new source set

Editing `digest.config.yaml` covers most of it — the competitor list and source
list are both plain YAML, and adding a competitor is one line.

For a genuinely different market you need three changes:

1. **`competitors:`** — the names to track.
2. **`sources:`** — add a key, then add a matching function to the `COLLECTORS`
   dict in `digest_agent.py`. Each collector takes `(competitors, opts)` and
   returns a list of dicts with a `competitor` key. That's the entire contract.
3. **`SYSTEM`** — the prompt encodes what "so what" means for *this* company.
   For a different company, the paragraph describing defensible ground is the
   part to rewrite. Everything else generalises.

The framing section of `index.html` — the mismatch between SaaS signal sources
and this market's signal sources — is the part that doesn't generalise. It's an
argument about this specific market and would need rewriting for another.

---

## Sourcing and limitations

Every claim in Issue 01 comes from a public announcement, published research, a
government budget document, or a company filing — each linked and dated in the
expanded detail of its entry, so any claim can be checked in one tap. No
confidential or insider information about Planet appears anywhere.

Three limits worth stating plainly:

- **One source has no URL.** Clay's Sentinel-2 embeddings on Source Cooperative
  are referenced via the LGND and Clay announcements rather than linked
  directly. It renders unlinked on the page for exactly that reason.

- **The trajectory section is argued interpretation, not sourced fact.** It's
  labelled as such on the page.
- **Contract-award coverage is limited to unclassified filings.** The classified
  portion of this market is, by construction, invisible to any workflow like this
  one. Anyone selling you complete coverage of the defense geospatial market is
  selling you something.
