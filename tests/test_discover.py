"""Tests for the source discovery script. No real network: a fake `fetch` answers instead.

All titles and DOIs below are obviously fake test data.
"""
import argparse
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import discover_sources as ds  # noqa: E402
from discover_sources import Blocked, Candidate, PoliteClient, Response  # noqa: E402


class FakeNet:
    """Maps URL prefixes to responses and records every request made."""

    def __init__(self, routes):
        self.routes = routes   # list of (prefix, Response or list of Responses)
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        for prefix, resp in self.routes:
            if url.startswith(prefix):
                if isinstance(resp, list):
                    return resp.pop(0) if len(resp) > 1 else resp[0]
                return resp
        return Response(404, {}, b"")


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def client(net, t=None, intervals=None):
    t = t or FakeTime()
    return PoliteClient(fetch=net, sleep=t.sleep, clock=t.clock, intervals=intervals or {}, log=lambda *_: None)


def ok(obj):
    return Response(200, {}, json.dumps(obj).encode())


# ---- politeness ----

def test_robots_disallow_blocks_without_calling_api():
    net = FakeNet([("https://example.org/robots.txt", Response(200, {}, b"User-agent: *\nDisallow: /"))])
    c = client(net)
    with pytest.raises(Blocked):
        c.get("https://example.org/api?q=x")
    assert [u for u, _ in net.calls] == ["https://example.org/robots.txt"]


def test_missing_robots_means_allowed():
    net = FakeNet([("https://example.org/api", ok({"a": 1}))])  # robots.txt -> 404
    assert json.loads(client(net).get("https://example.org/api?q=x")) == {"a": 1}


def test_robots_server_error_means_disallowed():
    net = FakeNet([("https://example.org/robots.txt", Response(500, {}, b""))])
    with pytest.raises(Blocked):
        client(net).get("https://example.org/api")


def test_crawl_delay_is_respected():
    net = FakeNet([("https://example.org/robots.txt", Response(200, {}, b"User-agent: *\nCrawl-delay: 10\n")),
                   ("https://example.org/api", ok({}))])
    t = FakeTime()
    c = client(net, t, intervals={"example.org": 1.0})
    c.get("https://example.org/api?1")
    c.get("https://example.org/api?2")
    assert sum(t.sleeps) >= 20          # robots -> call 1 -> call 2, each 10s apart


def test_retry_after_on_429():
    net = FakeNet([("https://example.org/api", [Response(429, {"Retry-After": "7"}, b""), ok({"done": True})])])
    t = FakeTime()
    assert json.loads(client(net, t).get("https://example.org/api")) == {"done": True}
    assert 7 in t.sleeps


def test_user_agent_has_no_personal_details(monkeypatch):
    monkeypatch.delenv("DISCOVERY_CONTACT_EMAIL", raising=False)
    net = FakeNet([("https://api.crossref.org/works", ok({"message": {"items": []}}))])
    ds.search_crossref(client(net), "x", 5, None)
    url, headers = net.calls[-1]
    assert "@" not in headers["User-Agent"] and "mailto" not in url


# ---- parsing each API ----

def test_parse_crossref():
    net = FakeNet([("https://api.crossref.org/works", ok({"message": {"items": [{
        "DOI": "10.0000/FAKE.1", "title": ["Fake Kushan paper"], "type": "journal-article",
        "author": [{"family": "Testova", "given": "A."}], "issued": {"date-parts": [[2021, 3]]},
        "container-title": ["Journal of Tests"], "URL": "https://doi.org/10.0000/FAKE.1"}]}}))])
    [c] = ds.search_crossref(client(net), "kushan", 5, 2015)
    assert (c.title, c.authors, c.year, c.doi, c.venue) == ("Fake Kushan paper", ["Testova, A."], 2021,
                                                           "10.0000/FAKE.1", "Journal of Tests")
    assert "from-pub-date%3A2015" in net.calls[-1][0]


def test_parse_openalex():
    net = FakeNet([("https://api.openalex.org/works", ok({"results": [{
        "id": "https://openalex.org/W1", "doi": "https://doi.org/10.0000/fake.2",
        "display_name": "Fake Saka genomes", "publication_year": 2020, "type": "preprint",
        "authorships": [{"author": {"display_name": "B. Testov"}}] * 7,
        "primary_location": {"source": {"display_name": "bioRxiv"}, "landing_page_url": "https://x.test/1"}}]}))])
    [c] = ds.search_openalex(client(net), "saka", 5, None)
    assert c.doi == "10.0000/fake.2" and c.source_type == "preprint"
    assert len(c.authors) == 6 and c.authors[-1] == "et al."


def test_parse_arxiv():
    atom = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><id>http://arxiv.org/abs/0000.0001</id><published>2019-05-01T00:00:00Z</published>
      <title>Fake  steppe
      model</title><author><name>C. Testman</name></author></entry></feed>"""
    net = FakeNet([("https://export.arxiv.org/api", Response(200, {}, atom))])
    [c] = ds.search_arxiv(client(net), "steppe model", 5, None)
    assert c.title == "Fake steppe model" and c.year == 2019 and c.source_type == "preprint"


def test_parse_europepmc():
    net = FakeNet([("https://www.ebi.ac.uk/europepmc", ok({"resultList": {"result": [{
        "id": "PPR1", "title": "Fake Bactria preprint.", "authorString": "Testa D, Testi E.",
        "pubYear": "2022", "doi": "10.0000/fake.3", "bookOrReportDetails": {"publisher": "bioRxiv"}}]}}))])
    [c] = ds.search_europepmc(client(net), "bactria", 5, None)
    assert (c.title, c.venue, c.authors) == ("Fake Bactria preprint", "bioRxiv", ["Testa D", "Testi E"])
    assert "SRC%3APPR" in net.calls[-1][0]


def test_parse_github():
    net = FakeNet([("https://api.github.com/search", ok({"items": [{
        "full_name": "tester/fake-adna", "html_url": "https://github.com/tester/fake-adna",
        "owner": {"login": "tester"}, "created_at": "2023-01-01T00:00:00Z", "license": {"spdx_id": "MIT"}}]}))])
    [c] = ds.search_github(client(net), "adna", 5, None)
    assert c.venue == "GitHub repository (MIT)" and c.source_type == "dataset"


# ---- the queue ----

def test_require_filter_and_dedup():
    net = FakeNet([("https://api.openalex.org/works", ok({"results": [
        {"display_name": "Fake Pashto phonology", "doi": "10.0000/new", "authorships": []},
        {"display_name": "Unrelated chemistry paper", "doi": "10.0000/noise", "authorships": []},
        {"display_name": "Already known Pashto work", "doi": "10.0000/known", "authorships": []}]}))])
    found = ds.run_search(client(net), [{"text": "pashto", "require": ["pashto"]}], ["openalex"], 5,
                          None, known={"doi:10.0000/known"}, log=lambda *_: None)
    assert [c.title for c in found.values()] == ["Fake Pashto phonology"]


def test_blocked_api_is_skipped_for_rest_of_run():
    net = FakeNet([("https://export.arxiv.org/robots.txt", Response(200, {}, b"User-agent: *\nDisallow: /"))])
    logs = []
    ds.run_search(client(net), [{"text": "a"}, {"text": "b"}], ["arxiv"], 5, None, set(), log=logs.append)
    assert len(net.calls) == 1                       # robots.txt only, once
    assert any("skipped" in line for line in logs)


def test_suggested_ids_are_unique():
    taken = {"testova-2021"}
    c = Candidate(title="x", authors=["Testová, A."], year=2021)
    assert ds.suggested_id(c, taken) == "testova-2021-2"


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    (tmp_path / "sources").mkdir()
    (tmp_path / "review-queue").mkdir()
    monkeypatch.setattr(ds, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ds, "QUEUE_DIR", tmp_path / "review-queue")
    return tmp_path


def test_promote_only_approved_with_summary(tmp_data):
    base = {"authors": ["Testova, A."], "year": 2021, "source_type": "journal-article",
            "venue": "J. Tests", "doi": "10.0000/p", "url": None, "found_via": ["openalex: x"],
            "reviewer_note": "", "key": "k"}
    queue = [
        dict(base, suggested_id="a-2021", status="approved", title="Approved one", summary="My own summary."),
        dict(base, suggested_id="b-2021", status="approved", title="No summary yet", summary=""),
        dict(base, suggested_id="c-2021", status="pending", title="Still pending", summary="x"),
    ]
    ds.save_queue(tmp_data / "review-queue" / "queue.yaml", queue)
    ds.cmd_promote(argparse.Namespace(), log=lambda *_: None)
    files = sorted(p.name for p in (tmp_data / "sources").iterdir())
    assert files == ["a-2021.yaml"]
    src = yaml.safe_load((tmp_data / "sources" / "a-2021.yaml").read_text())
    assert src["verification"]["status"] == "unverified" and src["summary"] == "My own summary."
    statuses = {e["suggested_id"]: e["status"] for e in yaml.safe_load((tmp_data / "review-queue" / "queue.yaml").read_text())}
    assert statuses == {"a-2021": "promoted", "b-2021": "approved", "c-2021": "pending"}


def test_promoted_source_passes_validation(tmp_data):
    """A promoted file must be a valid source file."""
    from jsonschema import Draft202012Validator
    queue = [{"suggested_id": "a-2021", "status": "approved", "title": "A fake test title", "authors": ["A, B."],
              "year": 2021, "source_type": "preprint", "venue": "bioRxiv", "doi": "10.0000/x", "url": None,
              "found_via": [], "summary": "Mine.", "reviewer_note": "", "key": "k"}]
    ds.save_queue(tmp_data / "review-queue" / "queue.yaml", queue)
    ds.cmd_promote(argparse.Namespace(), log=lambda *_: None)
    schema = json.loads((ROOT / "schema" / "source.schema.json").read_text())
    data = yaml.safe_load((tmp_data / "sources" / "a-2021.yaml").read_text())
    assert list(Draft202012Validator(schema).iter_errors(data)) == []


def test_exclude_words_drop_results():
    assert ds.title_matches("Pashtun ancestry study", ["pashtun"], ["cancer"])
    assert not ds.title_matches("Breast cancer risk among Pashtuns", ["pashtun"], ["cancer"])


def test_clean_title():
    assert ds.clean_title("The <i>Homo</i>  sapiens &amp; friends") == "The Homo sapiens & friends"
