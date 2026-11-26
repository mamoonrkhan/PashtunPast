"""Find candidate sources and put them in a review queue for a human.

Run:
  python scripts/discover_sources.py search              # run all searches
  python scripts/discover_sources.py search --apis openalex --limit 5 --since 2015
  python scripts/discover_sources.py search --dry-run    # print, don't write the queue
  python scripts/discover_sources.py promote             # turn approved entries into source files

How it works:
  1. Reads the searches from data/review-queue/queries.yaml.
  2. Asks each open API: Crossref, OpenAlex, arXiv, Europe PMC (for bioRxiv/medRxiv
     preprints) and GitHub. It stores METADATA ONLY: title, authors, year, venue,
     DOI and link. It never stores abstracts or full text, which are often
     copyrighted.
  3. Skips anything already in data/sources/ or already in the queue (including
     entries a reviewer rejected, so they don't keep coming back).
  4. Adds new candidates to data/review-queue/queue.yaml with status "pending".

A human then opens each candidate, writes a summary in their own words, and
sets status to "approved" or "rejected". `promote` turns approved entries into
data/sources/<id>.yaml files, still marked unverified.

Being a good citizen:
  * robots.txt is checked for every host, following RFC 9309. If a host
    disallows our path, we skip it and say so.
  * Each host gets a minimum gap between requests (the larger of our setting
    and the host's Crawl-delay), and 429/503 responses are retried after the
    time the server asks for.
  * Requests identify the project with a User-Agent. Contact details are only
    sent if YOU set DISCOVERY_CONTACT_EMAIL (Crossref and OpenAlex give faster
    service to clients that do). GitHub searches use GITHUB_TOKEN if it is set.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from atlas_data import DATA_DIR, load_yaml

QUEUE_DIR = DATA_DIR / "review-queue"
USER_AGENT = "PashtunOriginsProject-discovery/0.1 (open research atlas; metadata only)"
ROBOTS_AGENT = "PashtunOriginsProject-discovery"

# Minimum seconds between requests to each host (before any robots.txt Crawl-delay).
MIN_INTERVAL = {
    "api.crossref.org": 1.0,
    "api.openalex.org": 1.0,
    "export.arxiv.org": 3.0,        # arXiv asks for one request every 3 seconds
    "www.ebi.ac.uk": 1.0,           # robots.txt currently asks for 10s; that wins
    "api.github.com": 6.5,          # unauthenticated search: 10 requests per minute
}
PAPER_APIS = ["crossref", "openalex", "arxiv", "europepmc"]
ALL_APIS = PAPER_APIS + ["github"]


# --------------------------------------------------------------------------
# Polite HTTP
# --------------------------------------------------------------------------

class Blocked(Exception):
    """robots.txt says we may not fetch this URL."""


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes


def urllib_fetch(url: str, headers: dict) -> Response:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return Response(r.status, dict(r.headers), r.read())
    except urllib.error.HTTPError as e:
        return Response(e.code, dict(e.headers or {}), e.read() or b"")


class PoliteClient:
    """Checks robots.txt, waits between requests to the same host, and retries politely.

    `fetch`, `sleep` and `clock` can be replaced in tests so no real network is used.
    """

    def __init__(self, fetch: Callable[[str, dict], Response] = urllib_fetch,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic,
                 intervals: dict | None = None, log: Callable[[str], None] = print):
        self.fetch, self.sleep, self.clock, self.log = fetch, sleep, clock, log
        self.intervals = dict(MIN_INTERVAL if intervals is None else intervals)
        self.last_request: dict[str, float] = {}
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _wait_turn(self, host: str):
        gap = self.intervals.get(host, 1.0)
        last = self.last_request.get(host)
        if last is not None:
            remaining = gap - (self.clock() - last)
            if remaining > 0:
                self.sleep(remaining)
        self.last_request[host] = self.clock()

    def _robots_for(self, scheme: str, host: str):
        """Fetch and parse robots.txt once per host (RFC 9309 rules for errors)."""
        if host in self.robots:
            return self.robots[host]
        url = f"{scheme}://{host}/robots.txt"
        self._wait_turn(host)
        try:
            resp = self.fetch(url, {"User-Agent": USER_AGENT})
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            self.log(f"  ! could not read {url} ({e}); treating {host} as disallowed")
            resp = Response(503, {}, b"")
        rp = urllib.robotparser.RobotFileParser()
        if 200 <= resp.status < 300:
            rp.parse(resp.body.decode("utf-8", "replace").splitlines())
        elif 400 <= resp.status < 500:
            rp.parse([])                    # no robots.txt: everything allowed
        else:
            rp.parse(["User-agent: *", "Disallow: /"])  # server error: assume disallowed
        delay = rp.crawl_delay(ROBOTS_AGENT) or rp.crawl_delay("*")
        if delay:
            self.intervals[host] = max(self.intervals.get(host, 1.0), float(delay))
        self.robots[host] = rp
        return rp

    def get(self, url: str, headers: dict | None = None) -> bytes:
        parts = urllib.parse.urlsplit(url)
        rp = self._robots_for(parts.scheme, parts.netloc)
        if not rp.can_fetch(ROBOTS_AGENT, url):
            raise Blocked(f"robots.txt on {parts.netloc} disallows {parts.path}")
        hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
        for attempt in range(4):
            self._wait_turn(parts.netloc)
            resp = self.fetch(url, hdrs)
            if resp.status in (429, 503) and attempt < 3:
                retry_after = resp.headers.get("Retry-After", "")
                wait = min(float(retry_after) if retry_after.isdigit() else 5.0 * (attempt + 1), 60.0)
                self.log(f"  … {parts.netloc} asked us to slow down; waiting {wait:.0f}s")
                self.sleep(wait)
                continue
            if resp.status >= 400:
                raise urllib.error.HTTPError(url, resp.status, f"HTTP {resp.status}", None, None)
            return resp.body
        raise urllib.error.HTTPError(url, 429, "still rate-limited after retries", None, None)


# --------------------------------------------------------------------------
# Candidates and the five APIs
# --------------------------------------------------------------------------

@dataclass
class Candidate:
    title: str
    authors: list[str]
    year: int | None
    venue: str = ""
    doi: str = ""
    url: str = ""
    source_type: str = "journal-article"
    found_via: list[str] = field(default_factory=list)   # e.g. "openalex: Kushan empire"

    @property
    def key(self) -> str:
        return f"doi:{self.doi.lower()}" if self.doi else f"title:{norm_title(self.title)}"


def fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", fold(t)).strip()


def clean_title(title: str) -> str:
    """Some APIs return titles with HTML tags (<i>Homo</i>) or extra spaces."""
    return " ".join(re.sub(r"<[^>]+>", "", html.unescape(title or "")).split())


def clean_doi(doi: str | None) -> str:
    if not doi:
        return ""
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I)


def shorten_authors(names: list[str], keep: int = 5) -> list[str]:
    names = [n for n in names if n]
    return names[:keep] + (["et al."] if len(names) > keep else [])


def contact_params() -> dict:
    email = os.environ.get("DISCOVERY_CONTACT_EMAIL", "").strip()
    return {"mailto": email} if email else {}


def search_crossref(client: PoliteClient, query: str, limit: int, since: int | None) -> list[Candidate]:
    params = {"query.bibliographic": query, "rows": limit,
              "select": "DOI,title,author,issued,container-title,type,URL", **contact_params()}
    if since:
        params["filter"] = f"from-pub-date:{since}"
    data = json.loads(client.get("https://api.crossref.org/works?" + urllib.parse.urlencode(params)))
    out = []
    type_map = {"journal-article": "journal-article", "book": "book", "monograph": "book",
                "edited-book": "book", "book-chapter": "book-chapter", "posted-content": "preprint",
                "dataset": "dataset", "dissertation": "thesis"}
    for it in data.get("message", {}).get("items", []):
        title = (it.get("title") or [""])[0]
        if not title:
            continue
        authors = [", ".join(p for p in (a.get("family"), a.get("given")) if p) or a.get("name", "")
                   for a in it.get("author", [])]
        parts = (it.get("issued") or {}).get("date-parts") or [[None]]
        out.append(Candidate(
            title=title, authors=shorten_authors(authors), year=parts[0][0] if parts[0] else None,
            venue=(it.get("container-title") or [""])[0], doi=clean_doi(it.get("DOI")),
            url=it.get("URL", ""), source_type=type_map.get(it.get("type"), "journal-article")))
    return out


def search_openalex(client: PoliteClient, query: str, limit: int, since: int | None) -> list[Candidate]:
    params = {"search": query, "per-page": limit,
              "select": "id,doi,display_name,authorships,publication_year,primary_location,type",
              **contact_params()}
    if since:
        params["filter"] = f"publication_year:>{since - 1}"
    data = json.loads(client.get("https://api.openalex.org/works?" + urllib.parse.urlencode(params)))
    type_map = {"article": "journal-article", "book": "book", "book-chapter": "book-chapter",
                "preprint": "preprint", "dataset": "dataset", "dissertation": "thesis"}
    out = []
    for w in data.get("results", []):
        if not w.get("display_name"):
            continue
        loc = w.get("primary_location") or {}
        venue = ((loc.get("source") or {}).get("display_name")) or ""
        out.append(Candidate(
            title=w["display_name"],
            authors=shorten_authors([(a.get("author") or {}).get("display_name", "") for a in w.get("authorships", [])]),
            year=w.get("publication_year"), venue=venue, doi=clean_doi(w.get("doi")),
            url=loc.get("landing_page_url") or w.get("id", ""),
            source_type=type_map.get(w.get("type"), "journal-article")))
    return out


ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def search_arxiv(client: PoliteClient, query: str, limit: int, since: int | None) -> list[Candidate]:
    q = " AND ".join(f"all:{w}" for w in query.split())
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": q, "max_results": limit})
    root = ET.fromstring(client.get(url, {"Accept": "application/atom+xml"}))
    out = []
    for e in root.findall("a:entry", ATOM):
        title = " ".join((e.findtext("a:title", "", ATOM) or "").split())
        year = int((e.findtext("a:published", "", ATOM) or "0000")[:4]) or None
        if not title or (since and year and year < since):
            continue
        out.append(Candidate(
            title=title, authors=shorten_authors([a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)]),
            year=year, venue="arXiv", doi=clean_doi(e.findtext("arxiv:doi", "", ATOM)),
            url=e.findtext("a:id", "", ATOM), source_type="preprint"))
    return out


def search_europepmc(client: PoliteClient, query: str, limit: int, since: int | None) -> list[Candidate]:
    """Preprints (bioRxiv, medRxiv, …) via Europe PMC, because bioRxiv's own API has no keyword search."""
    q = f"({query}) AND SRC:PPR"
    if since:
        q += f" AND PUB_YEAR:[{since} TO 3000]"
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
           + urllib.parse.urlencode({"query": q, "format": "json", "pageSize": limit, "resultType": "lite"}))
    data = json.loads(client.get(url))
    out = []
    for r in (data.get("resultList") or {}).get("result", []):
        title = (r.get("title") or "").rstrip(".")
        if not title:
            continue
        publisher = (r.get("bookOrReportDetails") or {}).get("publisher", "") or "Preprint"
        authors = [a.strip() for a in (r.get("authorString") or "").rstrip(".").split(",")]
        doi = clean_doi(r.get("doi"))
        out.append(Candidate(
            title=title, authors=shorten_authors(authors),
            year=int(r["pubYear"]) if str(r.get("pubYear", "")).isdigit() else None,
            venue=publisher, doi=doi,
            url=f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/PPR/{r.get('id', '')}",
            source_type="preprint"))
    return out


def search_github(client: PoliteClient, query: str, limit: int, since: int | None) -> list[Candidate]:
    q = query + (f" pushed:>={since}-01-01" if since else "")
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": q, "per_page": limit})
    data = json.loads(client.get(url, headers))
    out = []
    for repo in data.get("items", []):
        licence = (repo.get("license") or {}).get("spdx_id") or "no licence stated"
        out.append(Candidate(
            title=repo["full_name"], authors=[(repo.get("owner") or {}).get("login", "")],
            year=int(repo["created_at"][:4]) if repo.get("created_at") else None,
            venue=f"GitHub repository ({licence})", url=repo.get("html_url", ""), source_type="dataset"))
    return out


SEARCHERS = {
    "crossref": search_crossref, "openalex": search_openalex, "arxiv": search_arxiv,
    "europepmc": search_europepmc, "github": search_github,
}


# --------------------------------------------------------------------------
# The review queue
# --------------------------------------------------------------------------

QUEUE_HEADER = """\
# REVIEW QUEUE — candidate sources found by scripts/discover_sources.py.
#
# For each entry:
#   1. Open the link and check that it is real and relevant.
#   2. Write `summary:` in YOUR OWN words (2–3 sentences). Never paste the abstract.
#   3. Set `status:` to approved or rejected (add a reason in reviewer_note).
#   4. Run `python scripts/discover_sources.py promote` to turn approved entries into
#      files in data/sources/ (they start as unverified).
# Rejected entries stay here so the script doesn't suggest them again.
"""


def suggested_id(c: Candidate, taken: set[str]) -> str:
    first = c.authors[0] if c.authors else c.title
    family = first.split(",")[0] if "," in first else first.split()[-1] if first.split() else "source"
    base = re.sub(r"[^a-z0-9]+", "-", fold(family)).strip("-") or "source"
    base = f"{base}-{c.year or 'nd'}"
    sid, n = base, 2
    while sid in taken:
        sid = f"{base}-{n}"
        n += 1
    taken.add(sid)
    return sid


def title_matches(title: str, require: list[str], exclude: list[str] = ()) -> bool:
    """Keep a result only if its title has a `require` word and no `exclude` word."""
    t = fold(title)
    if any(fold(w) in t for w in exclude):
        return False
    return not require or any(fold(w) in t for w in require)


def existing_keys() -> tuple[set[str], set[str]]:
    """Keys (DOI / normalised title) and IDs of sources already in data/sources/."""
    keys, ids = set(), set()
    for p in (DATA_DIR / "sources").glob("*.yaml"):
        s = load_yaml(p) or {}
        ids.add(s.get("id", p.stem))
        if s.get("doi"):
            keys.add(f"doi:{s['doi'].lower()}")
        if s.get("title"):
            keys.add(f"title:{norm_title(s['title'])}")
    return keys, ids


def load_queue(path: Path) -> list[dict]:
    return (load_yaml(path) or []) if path.exists() else []


def save_queue(path: Path, entries: list[dict]):
    order = {"pending": 0, "approved": 1, "promoted": 2, "rejected": 3}
    entries = sorted(entries, key=lambda e: (order.get(e.get("status"), 9), -e.get("score", 0), e.get("title", "")))
    path.write_text(QUEUE_HEADER + "\n" + yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=100),
                    encoding="utf-8")


def run_search(client: PoliteClient, queries: list[dict], apis: list[str], limit: int,
               since: int | None, known: set[str], log=print, exclude: list[str] = ()) -> dict[str, Candidate]:
    found: dict[str, Candidate] = {}
    skipped_hosts: set[str] = set()
    for q in queries:
        q_apis = [a for a in (q.get("apis") or PAPER_APIS) if a in apis]
        for api in q_apis:
            if api in skipped_hosts:
                continue
            log(f"[{api}] {q['text']}")
            try:
                results = SEARCHERS[api](client, q["text"], limit, since)
            except Blocked as e:
                log(f"  ✗ skipped: {e}. Not using {api} this run.")
                skipped_hosts.add(api)
                continue
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, ET.ParseError) as e:
                log(f"  ! {api} failed: {e}")
                continue
            kept = 0
            for c in results:
                c.title = clean_title(c.title)
                if not title_matches(c.title, q.get("require", []), [*exclude, *q.get("exclude", [])]):
                    continue
                if c.key in known or f"title:{norm_title(c.title)}" in known:
                    continue
                if c.key in found:
                    found[c.key].found_via.append(f"{api}: {q['text']}")
                else:
                    c.found_via = [f"{api}: {q['text']}"]
                    found[c.key] = c
                kept += 1
            log(f"  {len(results)} results, {kept} new and relevant")
    return found


def candidate_to_entry(c: Candidate, sid: str, today: str) -> dict:
    return {
        "suggested_id": sid,
        "status": "pending",
        "title": c.title,
        "authors": c.authors,
        "year": c.year,
        "venue": c.venue,
        "doi": c.doi or None,
        "url": c.url or None,
        "source_type": c.source_type,
        "found_via": c.found_via,
        "score": len({v.split(':')[0] for v in c.found_via}) + len(c.found_via),
        "first_seen": today,
        "summary": "",
        "reviewer_note": "",
        "key": c.key,
    }


def cmd_search(args, client: PoliteClient | None = None, log=print) -> int:
    config = load_yaml(QUEUE_DIR / "queries.yaml") or {}
    queries = config.get("queries", [])
    apis = args.apis.split(",") if args.apis else ALL_APIS
    unknown = set(apis) - set(SEARCHERS)
    if unknown:
        log(f"Unknown API(s): {', '.join(sorted(unknown))}. Choose from {', '.join(ALL_APIS)}.")
        return 2
    queue_path = QUEUE_DIR / "queue.yaml"
    queue = load_queue(queue_path)
    src_keys, src_ids = existing_keys()
    known = src_keys | {e.get("key") for e in queue} | {f"title:{norm_title(e.get('title', ''))}" for e in queue}

    client = client or PoliteClient(log=log)
    found = run_search(client, queries, apis, args.limit, args.since, known, log, config.get("exclude", []))

    taken = src_ids | {e.get("suggested_id") for e in queue}
    today = dt.date.today().isoformat()
    new_entries = [candidate_to_entry(c, suggested_id(c, taken), today) for c in found.values()]

    log(f"\n{len(new_entries)} new candidate(s).")
    if args.dry_run:
        for e in new_entries:
            log(f"  - {e['title']} ({e['year']}) {e['doi'] or e['url']}")
        log("Dry run: queue not changed.")
        return 0
    save_queue(queue_path, queue + new_entries)
    log(f"Queue now has {sum(1 for e in queue + new_entries if e.get('status') == 'pending')} pending "
        f"entr(ies): {queue_path.relative_to(DATA_DIR.parent)}")
    return 0


def cmd_promote(args, log=print) -> int:
    queue_path = QUEUE_DIR / "queue.yaml"
    queue = load_queue(queue_path)
    made = 0
    for e in queue:
        if e.get("status") != "approved":
            continue
        if not (e.get("summary") or "").strip():
            log(f"  ! {e['suggested_id']}: approved but has no summary yet; skipped")
            continue
        path = DATA_DIR / "sources" / f"{e['suggested_id']}.yaml"
        if path.exists():
            log(f"  ! {path.name} already exists; change suggested_id and run again")
            continue
        source = {
            "id": e["suggested_id"], "title": e["title"], "authors": e["authors"] or ["Unknown"],
            "year": e["year"], "source_type": e["source_type"],
            **({"venue": e["venue"]} if e.get("venue") else {}),
            **({"doi": e["doi"]} if e.get("doi") else {}),
            **({"url": e["url"]} if e.get("url") else {}),
            "summary": e["summary"].strip(),
            "verification": {"status": "unverified",
                             "notes": f"Found by discover_sources.py ({'; '.join(e.get('found_via', []))}). "
                                      f"Approved from the review queue; still needs a full check."},
        }
        path.write_text(yaml.safe_dump(source, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
        e["status"] = "promoted"
        made += 1
        log(f"  + data/sources/{path.name}")
    save_queue(queue_path, queue)
    log(f"Promoted {made} source(s). Run scripts/validate.py next.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="search the APIs and add candidates to the review queue")
    s.add_argument("--apis", help=f"comma-separated subset of: {','.join(ALL_APIS)}")
    s.add_argument("--limit", type=int, default=10, help="results per query per API (default 10)")
    s.add_argument("--since", type=int, help="only works published in or after this year")
    s.add_argument("--dry-run", action="store_true", help="print results without changing the queue")
    sub.add_parser("promote", help="turn approved queue entries into data/sources/ files")
    args = ap.parse_args(argv)
    return cmd_search(args) if args.cmd == "search" else cmd_promote(args)


if __name__ == "__main__":
    sys.exit(main())
