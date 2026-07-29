#!/usr/bin/env python3
"""
build.py — renders digest.json + template.html into a static index.html.

Content and presentation are deliberately separate. digest.json is the file a
PMM edits; template.html holds the CSS and page chrome; neither one needs the
other's skills. The published page stays plain static HTML with no JavaScript,
so it renders identically with JS blocked and prints cleanly.

    python build.py                      # digest.json -> index.html
    python build.py --check              # verify index.html is in sync, exit 1 if not

Strings in digest.json are trusted HTML fragments (hand-edited or human-approved,
never raw user input), so inline <b>/<em> work. Source URLs are the exception —
they are escaped and scheme-checked, because those come from the agent.
"""

import argparse
import html
import json
import sys
from urllib.parse import urlparse

DATA, TEMPLATE, OUT = "digest.json", "template.html", "index.html"


def safe_url(url: str | None) -> str | None:
    """Only http(s) links get rendered as links. Anything else renders as text."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return html.escape(url, quote=True)


def source_li(src: dict) -> str:
    """One source row. Linked when we have a URL, plainly unlinked when we don't —
    an unlinkable source should look different from a verifiable one."""
    title, date = src["title"], src.get("date", "")
    url = safe_url(src.get("url"))
    label = f'<a href="{url}" target="_blank" rel="noopener">{title}</a>' if url \
        else f'<span class="nolink">{title}</span>'
    return f'    <li>{label} <span class="d">· {date}</span></li>'


def render_entry(i: int, e: dict) -> str:
    tags = "".join(f'<span class="tag">{t}</span>' for t in e["tags"])
    detail = "".join(
        f'\n      <h4>{d["heading"]}</h4>\n      <p>{d["body"]}</p>'
        for d in e.get("detail", []))
    sources = "\n".join(source_li(s) for s in e.get("sources", []))

    return f"""
    <article class="entry">
      <div class="entry-top">
        <span class="rank">{i:02d}</span>
        <h3 class="name">{e["competitor"]}</h3>
        {tags}
      </div>
      <p class="sowhat">{e["so_what"]}</p>

      <div class="field">
        <span class="label">Signal</span>
        <p class="signal">{e["signal"]}</p>
      </div>

      <div class="action">
        <span class="label">Battlecard line</span>
        <p>{e["action"]}</p>
      </div>

      <details>
        <summary>Detail &amp; sources</summary>
        <div class="detail">{detail}
          <h4>Sources</h4>
          <ul class="srcs">
{sources}
          </ul>
        </div>
      </details>
    </article>"""


def render(data: dict, config_yaml: str) -> str:
    iss, mis, dig = data["issue"], data["mismatch"], data["digest"]
    traj, cfg = data["trajectory"], data["config_section"]

    byline = "<br>\n      ".join(iss["byline"])
    pairs = "\n".join(
        f'      <div class="pair"><div class="dead">{d}</div>'
        f'<div class="live">{l}</div></div>'
        for d, l in mis["pairs"])
    entries = "\n".join(render_entry(i, e) for i, e in enumerate(data["entries"], 1))
    trajectories = "\n".join(f"""
    <div class="traj">
      <span class="horizon">{t["horizon"]}</span>
      <h3>{t["title"]}</h3>
      <p>{t["body"]}</p>
      <div class="position"><b>Position now</b>{t["position"]}</div>
    </div>""" for t in traj["items"])
    planet_srcs = "\n".join(source_li(s) for s in traj.get("planet_sources", []))
    footer = "\n".join(
        f'    <h5>{f["heading"]}</h5>\n    <p>{f["body"]}</p>'
        for f in data["footer"])

    return f"""
  <header class="masthead">
    <p class="kicker">Issue {iss["number"]} <span class="sep">·</span> Week of {iss["date"]}</p>
    <h1>{iss["title"]}</h1>
    <p class="standfirst">{iss["standfirst"]}</p>
    <p class="byline">
      {byline}
    </p>
  </header>

  <section>
    <div class="sec-head">
      <span class="sec-num">01</span>
      <h2>{mis["heading"]}</h2>
    </div>
    <p class="lede">{mis["lede"]}</p>
    <div class="pairs">
{pairs}
    </div>
    <p class="pairs-note">{mis["note"]}</p>
  </section>

  <section>
    <div class="sec-head">
      <span class="sec-num">02</span>
      <h2>{dig["heading"]}</h2>
    </div>
    <p class="lede">{dig["lede"]}</p>
{entries}
  </section>

  <section>
    <div class="sec-head">
      <span class="sec-num">03</span>
      <h2>{traj["heading"]}</h2>
    </div>
    <p class="lede">{traj["lede"]}</p>
{trajectories}

    <blockquote>{traj["quote"]["lead"]} <span>{traj["quote"]["accent"]}</span></blockquote>
    <p class="qnote">{traj["quote"]["note"]}</p>

    <div class="risk">
      <span class="label">{traj["risk"]["label"]}</span>
      <p>{traj["risk"]["body"]}</p>
    </div>

    <details>
      <summary>Planet claims used above — sources</summary>
      <div class="detail">
        <h4>Sources</h4>
        <ul class="srcs">
{planet_srcs}
        </ul>
      </div>
    </details>
  </section>

  <section>
    <div class="sec-head">
      <span class="sec-num">04</span>
      <h2>{cfg["heading"]}</h2>
    </div>
    <p class="lede">{cfg["lede"]}</p>
<pre>{html.escape(config_yaml)}</pre>
    <p class="caption">{cfg["caption"]}</p>
  </section>

  <footer>
{footer}
    <p class="verified">Sources last verified {iss["verified"]} · built from digest.json</p>
  </footer>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify index.html matches digest.json; exit 1 if stale")
    args = ap.parse_args()

    data = json.load(open(DATA))
    template = open(TEMPLATE).read()
    config_yaml = open("digest.config.yaml").read().rstrip()

    page = template.replace("<!--CONTENT-->", render(data, config_yaml))

    if args.check:
        current = open(OUT).read() if __import__("os").path.exists(OUT) else ""
        if current != page:
            print(f"{OUT} is out of sync with {DATA}. Run: python build.py",
                  file=sys.stderr)
            sys.exit(1)
        print(f"{OUT} is in sync with {DATA}.")
        return

    open(OUT, "w").write(page)
    n_src = sum(len(e.get("sources", [])) for e in data["entries"])
    n_linked = sum(1 for e in data["entries"] for s in e.get("sources", [])
                   if safe_url(s.get("url")))
    print(f"Wrote {OUT} — {len(data['entries'])} entries, "
          f"{n_linked}/{n_src} sources linked.")


if __name__ == "__main__":
    main()
