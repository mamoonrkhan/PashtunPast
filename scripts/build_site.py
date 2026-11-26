"""Build the static website from the data files.

Run:  python scripts/build_site.py            -> writes the site to _site/
      python -m http.server -d _site 8000     -> preview at http://localhost:8000

How it works, in four steps:
  1. Load data/ and run the validator. If there are errors, stop: we never
     publish data that breaks the rules.
  2. Build a "model": the data plus things computed from it, such as
     two-way links between claims and which claims cite each source.
  3. Render HTML pages from the Jinja templates in site/templates/.
  4. Copy CSS, JavaScript and Leaflet into the output folder.

All links are relative ("../sources.html"), so the site works both at
username.github.io/repo-name/ and when opened locally.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from atlas_data import DATA_DIR, ROOT, load_dataset
from validate import DOC_CITATION, validate

SITE_SRC = ROOT / "site"
DEFAULT_OUT = ROOT / "_site"

# How a link reads from each end. A claim that "depends-on" another is, seen
# from the other claim, its "basis".
RELATION_LABELS = {
    "competes-with": ("Competes with", "Competes with"),
    "contradicts":   ("Contradicts", "Contradicted by"),
    "supports":      ("Supports", "Supported by"),
    "refines":       ("Refines", "Refined by"),
    "depends-on":    ("Depends on", "Is a basis for"),
}
COMPETING = {"competes-with", "contradicts"}

# How sure the evidence lets us be. `label` is the everyday wording shown on the
# site; the key is the precise term used in the data files.
STRENGTHS = {
    "strong":    {"label": "Well supported",
                  "text": "The cited evidence clearly supports the statement as worded."},
    "moderate":  {"label": "Fairly well supported",
                  "text": "Supported, but with real gaps or caveats."},
    "weak":      {"label": "Weakly supported",
                  "text": "Only thin support so far. Treat it as a possibility."},
    "contested": {"label": "Disputed",
                  "text": "Serious evidence or arguments on more than one side, or not yet tested."},
    "unknown":   {"label": "Not yet assessed",
                  "text": "No source has been added yet, so we can't say how strong it is."},
}
CATEGORIES = {
    "linguistics": "Language", "genetics": "DNA", "archaeology": "Archaeology",
    "history": "History", "origin-theory": "Origin theory",
}

# Everyday wording for the kinds of group in data/vocab/populations.yaml.
KIND_LABELS = {
    "ethnonym": "name of a people", "archaeological-culture": "archaeological culture",
    "genetic-cluster": "DNA grouping", "linguistic-group": "language group",
    "polity": "state or empire", "religious-community": "religious community",
}

# A discussion paragraph that starts with an ALL-CAPS lead-in ("WHAT POINTS TOWARDS IT.")
# is shown with that lead-in as a small heading.
LEAD_IN = re.compile(r"^([A-Z][A-Z' ,\-]{3,}[A-Z])\.\s+(.*)$", re.S)


def paragraphs(text: str) -> list[dict]:
    """Split a discussion into paragraphs; pull out ALL-CAPS lead-ins.

    In YAML's folded style (`discussion: >`) a blank line between paragraphs
    becomes a single newline, so any line break marks a new paragraph.
    """
    out = []
    for block in re.split(r"\n+", (text or "").strip()):
        block = " ".join(block.split())
        if not block:
            continue
        m = LEAD_IN.match(block)
        if m:
            out.append({"heading": m.group(1).capitalize(), "text": m.group(2)})
        else:
            out.append({"heading": "", "text": block})
    return out
# Category colours reuse the evidence palette so a colour means the same discipline everywhere.
CATEGORY_COLORS = {
    "genetics": "#0072B2", "linguistics": "#009E73", "archaeology": "#E69F00",
    "history": "#56B4E9", "origin-theory": "#CC79A7",
}


def format_year(y: int | None) -> str:
    if y is None:
        return ""
    return f"{-y} BCE" if y < 0 else f"{y} CE"


def text_color_for(hex_color: str) -> str:
    """Black or white text, whichever reads better on this background (WCAG luminance)."""
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return "#000000" if lum > 0.18 else "#ffffff"


def short_cite(source: dict) -> str:
    """'Narasimhan et al. (2019)', 'Sims-Williams & Cribb (1996)', 'Herodotus & Godley (430 BCE)'."""
    names = [a.split(",")[0].replace("(ed.)", "").replace("(trans.)", "").strip()
             for a in source["authors"] if a != "et al."]
    if "et al." in source["authors"] or len(names) > 2:
        who = f"{names[0]} et al."
    else:
        who = " & ".join(names)
    year = source["year"]
    return f"{who} ({format_year(year) if year < 0 else year})"


def build_model(ds) -> dict:
    """Turn the loaded files into one dictionary that templates and JavaScript use."""
    levels = [dict(l, text_color=text_color_for(l["color"])) for l in ds.vocab["evidence-levels"]]
    level_order = {l["id"]: i for i, l in enumerate(levels)}
    populations = {p["id"]: p for p in ds.vocab["populations"]}
    regions = {r["id"]: r for r in ds.vocab["regions"]}
    periods = {p["id"]: p for p in ds.vocab["periods"]}

    sources = {r.data["id"]: dict(r.data, cited_by=[], short_cite=short_cite(r.data)) for r in ds.sources}
    claims = {r.data["id"]: dict(r.data) for r in ds.claims}

    for c in claims.values():
        c.setdefault("discussion", "")
        c["discussion_paragraphs"] = paragraphs(c["discussion"])
        c.setdefault("tags", [])
        c["related"] = []
        c["url"] = f"claims/{c['id']}.html"
        c["evidence_levels"] = sorted({x["evidence_level"] for x in c["citations"]}, key=level_order.get)
        if c.get("period"):
            p = c["period"]
            p.setdefault("periods", [])
            p.setdefault("label", f"{format_year(p['start'])} – {format_year(p['end'])}")

    # Two-way related links: declared once, shown on both claims.
    for c in list(claims.values()):
        for rel in c.get("related_claims", []):
            forward, backward = RELATION_LABELS[rel["relation"]]
            other = claims[rel["claim"]]
            c["related"].append({"claim": other["id"], "relation": rel["relation"],
                                 "label": forward, "note": rel.get("note", "")})
            other["related"].append({"claim": c["id"], "relation": rel["relation"],
                                     "label": backward, "note": rel.get("note", "")})
    for c in claims.values():
        seen, unique = set(), []
        for r in c["related"]:  # drop duplicates if both sides declared the link
            key = (r["claim"], r["relation"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        c["related"] = unique
        c["competing"] = [r for r in unique if r["relation"] in COMPETING]
        c["other_related"] = [r for r in unique if r["relation"] not in COMPETING]

    for c in claims.values():
        for cit in c["citations"]:
            if c["id"] not in sources[cit["source"]]["cited_by"]:
                sources[cit["source"]]["cited_by"].append(c["id"])

    # Linguistics module: arrange each cognate set as {language id: [forms]} for the table.
    languages = list(ds.vocab["languages"])
    field_order = ["kinship", "numbers", "nature", "animals", "body", "society", "religion", "other"]
    cognates = []
    for r in ds.cognates:
        cs = dict(r.data)
        cs.setdefault("notes", "")
        cs.setdefault("notes_sources", [])
        cs.setdefault("claims", [])
        cs.setdefault("semantic_field", "other")
        cs["cells"] = {lang["id"]: [f for f in cs["forms"] if f["language"] == lang["id"]] for lang in languages}
        cs["all_verified"] = all(f["status"] == "verified" for f in cs["forms"])
        cognates.append(cs)
        for ref in [f["source"] for f in cs["forms"]] + [n["source"] for n in cs["notes_sources"]]:
            used = sources[ref].setdefault("used_in_cognates", [])
            if cs["id"] not in used:
                used.append(cs["id"])
    cognates.sort(key=lambda cs: (field_order.index(cs["semantic_field"]), cs["gloss"]))

    return {
        "levels": levels,
        "levels_by_id": {l["id"]: l for l in levels},
        "populations": populations,
        "regions": regions,
        "periods": periods,
        "strengths": STRENGTHS,
        "categories": CATEGORIES,
        "kind_labels": KIND_LABELS,
        "category_colors": CATEGORY_COLORS,
        "questions": [dict(q, claim_objs=[claims[cid] for cid in q["claims"]]) for q in ds.guides.get("questions", [])],
        "glossary": sorted(ds.guides.get("glossary", []), key=lambda g: g["term"].lower()),
        "languages": languages,
        "languages_by_id": {l["id"]: l for l in languages},
        "cognates": cognates,
        "claims": dict(sorted(claims.items(), key=lambda kv: kv[1]["title"].lower())),
        "sources": dict(sorted(sources.items(), key=lambda kv: (kv[1]["authors"][0].lower(), kv[1]["year"]))),
    }


LIST_ITEM = r"(?:[-*+]|\d+\.)[ \t]"
LIST_AFTER_TEXT = re.compile(rf"(?m)^((?![ \t]*{LIST_ITEM})[^\n|>#\s].*)\n([ \t]*{LIST_ITEM})")


def doc_slug(path: Path) -> str:
    return "index" if path.stem.lower() == "readme" else path.stem


def build_docs(ds, model: dict) -> list[dict]:
    """Turn docs/genetics/*.md into page dictionaries (title, order, html, url).

    Contributor Markdown may not contain raw HTML: '<' and '&' are escaped before
    rendering, so anything that looks like a tag is shown as text.
    """
    pages = []
    for doc in ds.docs:
        section = doc.path.parent.name          # e.g. "genetics"
        slug = doc_slug(doc.path)
        text = doc.body.replace("&", "&amp;").replace("<", "&lt;")
        # GitHub lets a list start right after a line of text; Python-Markdown needs a
        # blank line first. Add one so docs look the same in both places.
        text = LIST_AFTER_TEXT.sub(r"\1\n\n\2", text)
        html = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "toc"])
        # Links between docs are written as other-page.md so they also work on GitHub.
        html = re.sub(r'href="((?:\.\./[A-Za-z0-9_-]+/)?)([A-Za-z0-9_-]+)\.md(#[^"]*)?"',
                      lambda m: f'href="{m.group(1)}{doc_slug(Path(m.group(2)))}.html{m.group(3) or ""}"', html)

        def cite(m):
            s = model["sources"][m.group(1)]
            label = s["short_cite"].replace(" (", " ").rstrip(")")
            return f'[<a class="doc-cite" href="../sources.html#{s["id"]}">{label}</a>]'
        html = DOC_CITATION.sub(cite, html)
        title = doc.meta.get("title") or slug
        url = f"{section}/{slug}.html"
        for ref in set(DOC_CITATION.findall(doc.body)):
            model["sources"][ref].setdefault("cited_in_docs", []).append({"title": title, "url": url})
        pages.append({"title": title, "order": doc.meta.get("order", 99), "section": section,
                      "slug": slug, "url": url, "html": html, "source_path": str(doc.path.relative_to(ROOT))
                      if doc.path.is_relative_to(ROOT) else doc.path.name})
    return sorted(pages, key=lambda p: (p["section"], p["order"], p["title"]))


def browser_data(model: dict) -> dict:
    """The subset of the model the JavaScript needs (search, filters, timeline, map)."""
    keep = ("id", "title", "statement", "discussion", "status", "strength", "category",
            "populations", "regions", "period", "evidence_levels", "tags", "url", "competing")
    return {
        "claims": [{k: c.get(k) for k in keep} for c in model["claims"].values()],
        "levels": model["levels"],
        "populations": list(model["populations"].values()),
        "regions": list(model["regions"].values()),
        "periods": list(model["periods"].values()),
        "strengths": {k: v["label"] for k, v in model["strengths"].items()},
        "categories": model["categories"],
        "category_colors": model["category_colors"],
    }


def json_for_html(obj) -> str:
    """JSON that is safe to place inside a <script> tag ('</script>' in data can't break out)."""
    return (json.dumps(obj, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def load_geo(data_dir: Path, regions: dict) -> dict:
    features = []
    for r in regions.values():
        if r.get("geo"):
            features += json.loads((data_dir / "geo" / r["geo"]).read_text(encoding="utf-8"))["features"]
    return {"type": "FeatureCollection", "features": features}


def build(data_dir: Path = DATA_DIR, out: Path = DEFAULT_OUT) -> int:
    ds = load_dataset(data_dir)
    errors, warnings = validate(ds)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"\nBuild stopped: {len(errors)} validation error(s). Run scripts/validate.py for details.")
        return 1

    model = build_model(ds)
    config = yaml.safe_load((SITE_SRC / "config.yaml").read_text(encoding="utf-8"))

    env = Environment(
        loader=FileSystemLoader(SITE_SRC / "templates"),
        autoescape=select_autoescape(["html"]),  # data text is escaped, so it can't inject HTML
        undefined=StrictUndefined,               # a typo in a template fails loudly
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters["year"] = format_year
    env.filters["tojson_html"] = json_for_html

    common = dict(m=model, config=config, built=dt.date.today().isoformat())
    data_json = json_for_html(browser_data(model))

    if out.exists():
        shutil.rmtree(out)
    (out / "claims").mkdir(parents=True)
    docs = build_docs(ds, model)   # before rendering Sources, which lists doc citations

    def render(template: str, path: str, **ctx):
        root = "../" * path.count("/")
        html = env.get_template(template).render(**common, root=root, page=path, **ctx)
        (out / path).write_text(html, encoding="utf-8")

    render("index.html", "index.html")
    render("claims_list.html", "claims.html", data_json=data_json)
    render("glossary.html", "glossary.html")
    render("timeline.html", "timeline.html", data_json=data_json)
    render("map.html", "map.html", data_json=data_json,
           geo_json=json_for_html(load_geo(data_dir, model["regions"])))
    render("sources.html", "sources.html")
    render("linguistics.html", "linguistics.html")
    render("methodology.html", "methodology.html")
    for c in model["claims"].values():
        render("claim.html", f"claims/{c['id']}.html", c=c)
    for d in docs:
        (out / d["section"]).mkdir(exist_ok=True)
        render("doc.html", d["url"], doc=d, section_docs=[x for x in docs if x["section"] == d["section"]])

    shutil.copytree(SITE_SRC / "static", out / "static")
    (out / ".nojekyll").write_text("")  # tell GitHub Pages to serve files as-is

    print(f"Built {len(model['claims'])} claim pages, {len(docs)} doc pages + 8 other pages into {out}"
          f" ({len(warnings)} validation warning(s)).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    return build(args.data_dir, args.out)


if __name__ == "__main__":
    sys.exit(main())
