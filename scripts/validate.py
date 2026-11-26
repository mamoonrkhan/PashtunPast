"""Check every data file against the project's rules.

Run:  python scripts/validate.py              (offline checks)
      python scripts/validate.py --check-dois (also asks Crossref whether each DOI exists)

Exit code 0 = all good, 1 = errors found. GitHub Actions runs this on every
pull request, so data that breaks a rule cannot be merged.

The rules (R1–R9) are listed in the docstring of `validate()` below.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from atlas_data import DATA_DIR, SCHEMA_DIR, Dataset, load_dataset

STRENGTH_RANK = {"weak": 1, "moderate": 2, "strong": 3}
DOC_CITATION = re.compile(r"\[@([a-z0-9]+(?:-[a-z0-9]+)*)\]")   # [@narasimhan-2019] in Markdown docs


def _schema_validator(name: str, ref: str | None = None) -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    if ref:  # validate against one sub-definition, e.g. vocab.schema.json#/$defs/regions
        schema = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{ref}"}
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _schema_errors(validator: Draft202012Validator, data, where: str) -> list[str]:
    out = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "(top level)"
        out.append(f"{where}: [R1 schema] {loc}: {err.message}")
    return out


def validate(ds: Dataset) -> tuple[list[str], list[str]]:
    """Return (errors, warnings).

    R1  Every file matches its JSON Schema (required fields, allowed values).
    R2  IDs are unique and each file is named <id>.yaml.
    R3  Everything a claim points to exists: sources, evidence levels,
        populations, regions, periods and related claims.
    R4  Dates make sense: start <= end, and no year 0.
    R5  An unverified claim must say what needs checking (verification_note).
    R6  A claim can only be 'verified' if it has citations and every source
        it cites has itself been verified by a human.
    R7  Strength cannot exceed the evidence: a claim rated strong/moderate/weak
        needs at least one supporting citation, and its rating cannot be above
        the best `max_strength` among them (e.g. legend alone -> at most moderate).
    R8  A 'contested' claim must show the contest: a contradicting citation or
        a competes-with/contradicts link to another claim (in either direction).
    R9  No claim links to itself, and no two sources share a DOI.
    """
    errors: list[str] = list(ds.load_errors)
    warnings: list[str] = []

    # R1 for vocabularies
    for name, entries in ds.vocab.items():
        errors += _schema_errors(_schema_validator("vocab.schema.json", name), entries, f"data/vocab/{name}.yaml")

    # R1 + R2 for sources and claims
    def check_files(records, schema_name, kind):
        v = _schema_validator(schema_name)
        seen: dict[str, Path] = {}
        for r in records:
            if not isinstance(r.data, dict):
                errors.append(f"{r.path}: [R1 schema] file must be a YAML mapping (key: value pairs)")
                continue
            errors.extend(_schema_errors(v, r.data, str(r.path)))
            rid = r.data.get("id")
            if rid is None:
                continue
            if rid != r.path.stem:
                errors.append(f"{r.path}: [R2 ids] id '{rid}' must match file name '{r.path.stem}'")
            if rid in seen:
                errors.append(f"{r.path}: [R2 ids] duplicate {kind} id '{rid}' (also in {seen[rid]})")
            seen[rid] = r.path
        return {r.data["id"]: r for r in records if isinstance(r.data, dict) and "id" in r.data}

    sources = check_files(ds.sources, "source.schema.json", "source")
    claims = check_files(ds.claims, "claim.schema.json", "claim")

    levels = ds.vocab_by_id("evidence-levels")
    populations = ds.vocab_ids("populations")
    regions = ds.vocab_ids("regions")
    periods = ds.vocab_ids("periods")

    # R3 for map shapes: each region's GeoJSON file must exist
    geo_dir = ds.data_dir / "geo"
    for reg in ds.vocab.get("regions", []):
        if isinstance(reg, dict) and reg.get("geo") and not (geo_dir / reg["geo"]).is_file():
            errors.append(f"data/vocab/regions.yaml: [R3 links] region '{reg.get('id')}' points to "
                          f"missing map file data/geo/{reg['geo']}")

    # R4 for the periods vocabulary
    for p in ds.vocab.get("periods", []):
        if isinstance(p, dict) and isinstance(p.get("start"), int) and isinstance(p.get("end"), int):
            if p["start"] > p["end"]:
                errors.append(f"data/vocab/periods.yaml: [R4 dates] period '{p.get('id')}' starts after it ends")

    # R9 duplicate DOIs
    doi_owner: dict[str, str] = {}
    for sid, r in sources.items():
        doi = r.data.get("doi")
        if doi:
            key = doi.lower()
            if key in doi_owner:
                errors.append(f"{r.path}: [R9 dupes] DOI {doi} is already used by source '{doi_owner[key]}'")
            doi_owner[key] = sid

    # Links declared from the other side (for R8 and the bidirectional warning)
    incoming: dict[str, list[tuple[str, str]]] = {}
    for cid, r in claims.items():
        for rel in r.data.get("related_claims", []) or []:
            if isinstance(rel, dict):
                incoming.setdefault(rel.get("claim"), []).append((cid, rel.get("relation")))

    cited_sources: set[str] = set()

    for cid, r in claims.items():
        c, where = r.data, str(r.path)

        # R3 vocab references
        for field_name, allowed, label in (("populations", populations, "population"),
                                            ("regions", regions, "region")):
            for value in c.get(field_name, []) or []:
                if value not in allowed:
                    errors.append(f"{where}: [R3 links] unknown {label} '{value}' (add it to data/vocab/{field_name}.yaml?)")
        period = c.get("period") or {}
        for value in period.get("periods", []) or []:
            if value not in periods:
                errors.append(f"{where}: [R3 links] unknown period '{value}'")

        # R4 dates
        start, end = period.get("start"), period.get("end")
        if isinstance(start, int) and isinstance(end, int):
            if 0 in (start, end):
                errors.append(f"{where}: [R4 dates] there is no year 0; use -1 for 1 BCE or 1 for 1 CE")
            if start > end:
                errors.append(f"{where}: [R4 dates] period start ({start}) is after end ({end})")

        # R3 citations, and gather info for R6/R7/R8
        citations = [x for x in (c.get("citations") or []) if isinstance(x, dict)]
        supporting_caps = []
        has_contradicting = False
        all_sources_verified = True
        for cit in citations:
            sid, lvl = cit.get("source"), cit.get("evidence_level")
            src = sources.get(sid)
            if src is None:
                errors.append(f"{where}: [R3 links] cites unknown source '{sid}' (no data/sources/{sid}.yaml)")
                all_sources_verified = False
            else:
                cited_sources.add(sid)
                if (src.data.get("verification") or {}).get("status") != "verified":
                    all_sources_verified = False
                if lvl == "peer-reviewed-genetics" and src.data.get("peer_reviewed") is False:
                    warnings.append(f"{where}: source '{sid}' is marked not peer-reviewed but cited as peer-reviewed-genetics")
            if lvl not in levels:
                errors.append(f"{where}: [R3 links] unknown evidence level '{lvl}'")
            elif cit.get("relation") == "supports":
                supporting_caps.append(STRENGTH_RANK[levels[lvl]["max_strength"]])
            if cit.get("relation") == "contradicts":
                has_contradicting = True

        # Warning: every claim should have an "In plain words" summary for general readers
        if not (c.get("plain") or "").strip():
            warnings.append(f"{where}: no 'plain' summary; add one or two sentences in everyday language")

        # R5 / R6 verification
        status = c.get("status")
        if status == "unverified" and not (c.get("verification_note") or "").strip():
            errors.append(f"{where}: [R5 verify] unverified claims need a verification_note saying what to check")
        if status == "verified":
            if not citations:
                errors.append(f"{where}: [R6 verify] a verified claim needs at least one citation")
            elif not all_sources_verified:
                errors.append(f"{where}: [R6 verify] marked verified, but not every cited source is verified")

        # R7 strength vs evidence
        strength = c.get("strength")
        if strength in STRENGTH_RANK:
            if not supporting_caps:
                errors.append(f"{where}: [R7 strength] rated '{strength}' but has no supporting citation; "
                              f"use 'unknown' until a source is added")
            elif STRENGTH_RANK[strength] > max(supporting_caps):
                best = [k for k, v in STRENGTH_RANK.items() if v == max(supporting_caps)][0]
                errors.append(f"{where}: [R7 strength] rated '{strength}' but the supporting evidence "
                              f"only allows up to '{best}'")

        # R3 / R9 related claims
        competing = False
        for rel in c.get("related_claims", []) or []:
            if not isinstance(rel, dict):
                continue
            other = rel.get("claim")
            if other == cid:
                errors.append(f"{where}: [R9 self-link] claim links to itself")
            elif other not in claims:
                errors.append(f"{where}: [R3 links] related claim '{other}' does not exist")
            if rel.get("relation") in ("competes-with", "contradicts"):
                competing = True
        competing = competing or any(rel in ("competes-with", "contradicts")
                                     for _, rel in incoming.get(cid, []))

        # R8 contested must show the contest
        if strength == "contested" and not (has_contradicting or competing):
            errors.append(f"{where}: [R8 contested] 'contested' needs a contradicting citation "
                          f"or a competes-with/contradicts link to another claim")

    # Cognate sets (linguistics module)
    #   C1 schema + id matches file name (via check_files)
    #   C2 every language exists in data/vocab/languages.yaml
    #   C3 every source and linked claim exists
    #   C4 a form marked verified must cite a verified source
    languages = ds.vocab_ids("languages")
    cognates = check_files(ds.cognates, "cognate.schema.json", "cognate set")
    for sid_, r in cognates.items():
        where = str(r.path)
        cs = r.data
        refs = [f.get("source") for f in cs.get("forms", []) if isinstance(f, dict)]
        refs += [n.get("source") for n in cs.get("notes_sources", []) or [] if isinstance(n, dict)]
        if isinstance(cs.get("proto"), dict):
            refs.append(cs["proto"].get("source"))
            if cs["proto"].get("language") not in languages | {"proto-iranian", "proto-indo-iranian"}:
                errors.append(f"{where}: [C2 language] unknown proto-language '{cs['proto'].get('language')}'")
        for ref in refs:
            if ref is None:  # missing field: already reported by the schema check (R1)
                continue
            if ref not in sources:
                errors.append(f"{where}: [C3 links] cites unknown source '{ref}'")
            else:
                cited_sources.add(ref)
        for f in cs.get("forms", []):
            if not isinstance(f, dict):
                continue
            if f.get("language") not in languages:
                errors.append(f"{where}: [C2 language] unknown language '{f.get('language')}' "
                              f"(add it to data/vocab/languages.yaml?)")
            src = sources.get(f.get("source"))
            if f.get("status") == "verified" and src and src.data["verification"]["status"] != "verified":
                errors.append(f"{where}: [C4 verify] form '{f.get('form')}' is verified but its source "
                              f"'{f.get('source')}' is not")
        for cid in cs.get("claims", []) or []:
            if cid not in claims:
                errors.append(f"{where}: [C3 links] linked claim '{cid}' does not exist")

    # Docs (e.g. docs/genetics/*.md) cite sources as [@source-id]
    #   D1 every cited id must exist in data/sources/
    for doc in ds.docs:
        for ref in DOC_CITATION.findall(doc.body):
            if ref not in sources:
                errors.append(f"{doc.path}: [D1 links] cites unknown source '{ref}'")
            else:
                cited_sources.add(ref)

    # Plain-language guides (data/guides/)
    #   G1 schema; every claim a big question links to exists; glossary ids unique
    for name, entries in ds.guides.items():
        errors += _schema_errors(_schema_validator("guide.schema.json", name), entries, f"data/guides/{name}.yaml")
    for q in ds.guides.get("questions", []):
        for cid in (q.get("claims") or []) if isinstance(q, dict) else []:
            if cid not in claims:
                errors.append(f"data/guides/questions.yaml: [G1 links] question '{q.get('id')}' links unknown claim '{cid}'")
    seen_terms = set()
    for g in ds.guides.get("glossary", []):
        if isinstance(g, dict) and g.get("id") in seen_terms:
            errors.append(f"data/guides/glossary.yaml: [G1 ids] duplicate glossary id '{g.get('id')}'")
        if isinstance(g, dict):
            seen_terms.add(g.get("id"))

    # Warning: the same pair linked from both sides with different relations
    for cid, r in claims.items():
        for rel in r.data.get("related_claims", []) or []:
            if not isinstance(rel, dict):
                continue
            for back_from, back_rel in incoming.get(cid, []):
                if back_from == rel.get("claim") and back_rel != rel.get("relation"):
                    warnings.append(f"{r.path}: link to '{back_from}' is '{rel.get('relation')}' here "
                                    f"but '{back_rel}' on the other side")

    for sid, r in sources.items():
        # Warning: sources nobody cites
        if sid not in cited_sources:
            warnings.append(f"{r.path}: source is not cited by any claim")
        # Warning: no way for a reader to find it online (fine for old print works, but worth adding)
        if not any(r.data.get(k) for k in ("doi", "url", "isbn")) and r.data.get("source_type") != "primary-text":
            warnings.append(f"{r.path}: no doi, url or isbn; add one if it exists")

    return errors, warnings


def check_dois(ds: Dataset, delay: float = 1.0) -> list[str]:
    """Ask the Crossref API whether each DOI exists. Returns warnings.

    Uses a generic User-Agent (Crossref asks for one), one request per second.
    """
    out = []
    headers = {"User-Agent": "PashtunOriginsProject-validator/0.1 (open research atlas)"}
    for r in ds.sources:
        doi = r.data.get("doi") if isinstance(r.data, dict) else None
        if not doi:
            continue
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as resp:
                msg = json.load(resp)["message"]
                found_title = (msg.get("title") or [""])[0]
                out.append(f"{r.path}: DOI OK -> \"{found_title[:90]}\" — compare with our title")
        except urllib.error.HTTPError as e:
            out.append(f"{r.path}: DOI {doi} NOT FOUND on Crossref (HTTP {e.code}) — check it by hand")
        except (urllib.error.URLError, TimeoutError) as e:
            out.append(f"{r.path}: could not reach Crossref for {doi}: {e}")
        time.sleep(delay)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--check-dois", action="store_true", help="look up each DOI on Crossref (needs internet)")
    args = ap.parse_args(argv)

    ds = load_dataset(args.data_dir)
    errors, warnings = validate(ds)
    if args.check_dois:
        warnings += check_dois(ds)

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR:   {e}")
    print(f"\nChecked {len(ds.claims)} claims and {len(ds.sources)} sources: "
          f"{len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
