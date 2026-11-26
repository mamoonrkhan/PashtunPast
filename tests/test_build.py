"""Tests for the site builder."""
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_site import build, format_year, json_for_html, short_cite  # noqa: E402


def test_real_site_builds(tmp_path):
    out = tmp_path / "site"
    assert build(out=out) == 0
    claims = list((ROOT / "data" / "claims").glob("*.yaml"))
    assert len(list((out / "claims").glob("*.html"))) == len(claims)
    for page in ("index.html", "timeline.html", "map.html", "sources.html", "methodology.html"):
        assert (out / page).is_file()
    assert (out / "static" / "vendor" / "leaflet" / "leaflet.js").is_file()


def test_links_show_on_both_claims(tmp_path):
    out = tmp_path / "site"
    build(out=out)
    # lost-tribes-descent declares "competes-with pashtuns-steppe-ancestry";
    # the steppe-ancestry page must show the link back.
    page = (out / "claims" / "pashtuns-steppe-ancestry.html").read_text()
    assert "lost-tribes-descent.html" in page
    assert "Competing claims" in page


def test_contributor_text_cannot_inject_html(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "vocab", data / "vocab")
    shutil.copytree(ROOT / "data" / "geo", data / "geo")
    (data / "sources").mkdir()
    (data / "claims").mkdir()
    evil = "<script>alert(1)</script>"
    claim = {
        "id": "evil", "title": f"Title {evil}", "statement": f"Statement long enough {evil}",
        "status": "unverified", "verification_note": "x", "strength": "unknown",
        "category": "history", "populations": ["pashtuns"], "regions": [], "citations": [],
    }
    (data / "claims" / "evil.yaml").write_text(yaml.safe_dump(claim))
    out = tmp_path / "site"
    assert build(data_dir=data, out=out) == 0
    for page in (out / "claims" / "evil.html", out / "index.html", out / "timeline.html"):
        assert evil not in page.read_text(), page


def test_helpers():
    assert format_year(-480) == "480 BCE"
    assert format_year(127) == "127 CE"
    assert "</script>" not in json_for_html({"x": "</script>"})
    assert short_cite({"authors": ["A, B.", "et al."], "year": 2019}) == "A et al. (2019)"
    assert short_cite({"authors": ["A, B.", "C, D."], "year": 1996}) == "A & C (1996)"


def test_linguistics_page(tmp_path):
    out = tmp_path / "site"
    build(out=out)
    page = (out / "linguistics.html").read_text()
    assert "پلار" in page            # Pashto script rendered as text
    assert 'dir="auto"' in page      # right-to-left handled by the browser
    assert "sources.html#morgenstierne-2003" in page


def _docs_dataset(tmp_path, body):
    data = tmp_path / "data"
    for sub in ("vocab", "geo", "sources"):
        shutil.copytree(ROOT / "data" / sub, data / sub)
    (data / "claims").mkdir()
    (tmp_path / "docs" / "genetics").mkdir(parents=True)
    (tmp_path / "docs" / "genetics" / "page.md").write_text(f"---\ntitle: Test page\n---\n\n{body}\n")
    return data


def test_doc_citations_links_and_escaping(tmp_path):
    data = _docs_dataset(tmp_path, "See [@narasimhan-2019] and [next](other.md). <script>alert(1)</script>")
    out = tmp_path / "site"
    assert build(data_dir=data, out=out) == 0
    html = (out / "genetics" / "page.html").read_text()
    assert 'href="../sources.html#narasimhan-2019"' in html
    assert 'href="other.html"' in html
    assert "<script>alert(1)" not in html


def test_doc_with_unknown_citation_fails(tmp_path):
    data = _docs_dataset(tmp_path, "Made up [@nobody-1999].")
    assert build(data_dir=data, out=tmp_path / "site") == 1


def test_list_right_after_text_becomes_a_list(tmp_path):
    data = _docs_dataset(tmp_path, "Good for:\n- one\n- two\n\n1. first\n   continued\n2. second")
    out = tmp_path / "site"
    build(data_dir=data, out=out)
    html = (out / "genetics" / "page.html").read_text()
    assert "<li>one</li>" in html and "<li>two</li>" in html
    article = html.split("<article class=\"doc\">")[1]
    assert article.count("<ol>") == 1 and "<p>first" not in article


def test_cross_section_doc_links_and_heading_ids(tmp_path):
    out = tmp_path / "site"
    build(out=out)
    html = (out / "design" / "v2.html").read_text()
    assert 'href="../genetics/v2-analysis-plan.html"' in html
    assert 'id="1-pca-visualisation"' in html and 'href="#1-pca-visualisation"' in html
