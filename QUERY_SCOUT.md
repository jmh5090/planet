# query-scout

Stage one of a data-storytelling pipeline for Planet's **Queryable Earth** (an
agentic AI that answers natural-language questions from satellite imagery).

`query-scout` reads recent news and proposes ranked **post candidates**: for each
story that survives two hard filters, it names the dormant non-GIS buyer, the
question they'd ask, and the exact natural-language prompt to paste into the beta.
A human runs the top prompts in the beta by hand. **The tool never touches the
beta.**

```
config → ingest(news) → analyze(Claude) → rank → deliver(notifier)
```

## Running it — double-click (recommended for non-engineers)

One-time setup:

1. `pip install anthropic feedparser`
2. `cp .env.example .env`, then put your key in `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
3. The very first time, **right-click `Run Query Scout.command` → Open** (not a
   double-click) — macOS blocks a first double-click on an unsigned local
   script and needs that one explicit approval.

After that: **double-click `Run Query Scout.command`.** It runs the pipeline and
opens the finished report in your browser automatically. If something goes
wrong (missing key, network error), the window stays open with the error
message instead of vanishing.

## Running it — terminal

```bash
pip install anthropic feedparser
export ANTHROPIC_API_KEY=sk-ant-...   # or use .env, see above

./run.sh                     # full pipeline, deliver via the configured channel (html)
./run.sh --notify console    # print the ranked digest to the terminal
./run.sh --dry-run           # ingest + analyze, print JSON, deliver nothing
./run.sh --json out.json     # also write the ranked candidates to out.json
```

`run.sh` is the one-command wrapper — the same command works on-demand and as a
weekly cron / Task Scheduler entry:

```cron
0 6 * * 1  /path/to/planet/run.sh
```

Under the hood it is `python query_scout.py run [flags]`. The `html` channel
always writes both a dated file and `output_dir/latest.html` — the double-click
launcher opens `latest.html` so it never has to guess a filename.

## The analysis

Two **hard filters** drop anything that fails (no softening):

- **Satellite-visibility** — keep only changes observable from orbit at ~3 m over
  days-to-years (construction, deforestation, water/reservoir levels, flooding,
  burn scars, ports/shipping, mining, energy buildout, crop change, storage
  tanks). Reject policy, prices, earnings, rulings, sentiment, indoor/personal,
  sub-metre detail.
- **Safe-lane** — reject active-conflict / military / OSINT-sensitive topics.
  Planet has defense customers; freelancing on these publicly is off-limits.
  Favour economic, environmental, civic, commercial.

What survives is scored 1–10 on **longitudinal_moat** (the primary rank key — how
much the answer depends on frequent, longitudinal imagery rather than one
snapshot), **virality**, and **confidence**. Output is ranked by longitudinal
moat first, then virality + confidence.

## Slow-day fallback: day → week

Every run first pulls news from the last `lookback_days` (default: 1 day). If
that comes back with fewer than `min_candidates` (default: 3) passing
candidates — a slow news day — it automatically re-pulls from the last
`week_lookback_days` (default: 7) instead of shipping a thin report. The report
itself is labelled **Daily** or **Weekly** so it's always clear which window
produced it; nothing about a run is silently stretched without saying so.

## Config — `queryscout.config.json`

| Key | Meaning |
|---|---|
| `source` | Ingest source: `rss` (default), or add `newsapi` / `gdelt` in `SOURCES`. |
| `feeds` | RSS feed URLs (used by the `rss` source). |
| `max_items` | Cap on ingested stories sent to the model. |
| `model` | Anthropic model (default `claude-sonnet-4-6`). |
| `notify` | Default delivery channel. |
| `top_n` | How many top-ranked candidates to deliver. |
| `output_dir` | Where the `html` channel writes reports. |
| `lookback_days` | Daily news window in days (default `1`). |
| `week_lookback_days` | Widened window used on a slow day (default `7`). |
| `min_candidates` | Below this many passing candidates, retry with the wider window (default `3`). |

Swapping the news source means adding one function to the `SOURCES` registry that
returns a list of `{title, source, url, summary}` dicts — nothing downstream
changes.

## Delivery channels — `--notify html|email|slack|console`

Default is `html`. If a channel's required environment variable is missing, the
run fails and names the variable.

| Channel | Required environment variables |
|---|---|
| `html` | *(none)* — writes `output_dir/query-scout-YYYY-MM-DD.html` and `output_dir/latest.html` |
| `console` | *(none)* — prints to the terminal |
| `slack` | `SLACK_WEBHOOK_URL` |
| `email` | `QUERYSCOUT_SMTP_HOST`, `QUERYSCOUT_SMTP_USER`, `QUERYSCOUT_SMTP_PASSWORD`, `QUERYSCOUT_EMAIL_FROM`, `QUERYSCOUT_EMAIL_TO` (optional `QUERYSCOUT_SMTP_PORT`, default 587) |

Channels are a pluggable notifier interface — add one by writing a
`deliver(candidates, config, window_days)` function and registering it in
`NOTIFIERS` with the env vars it needs.
