"""Tests for the data rules.

Each test builds a tiny throwaway dataset in a temp folder, breaks ONE rule,
and checks the validator catches it. The sources here are obviously fake
test fixtures; they never go in data/.
"""
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from atlas_data import load_dataset  # noqa: E402
from validate import validate        # noqa: E402


def good_source(**over):
    s = {
        "id": "testauthor-2000",
        "title": "A test fixture, not a real source",
        "authors": ["Testauthor, A."],
        "year": 2000,
        "source_type": "journal-article",
        "peer_reviewed": True,
        "url": "https://example.org/fixture",
        "verification": {"status": "verified", "checked_by": "tester", "checked_on": "2026-01-01"},
    }
    s.update(over)
    return s


def good_claim(**over):
    c = {
        "id": "test-claim",
        "title": "A test claim",
        "statement": "This is a test claim used only by the test suite.",
        "status": "verified",
        "strength": "strong",
        "category": "history",
        "populations": ["pashtuns"],
        "regions": ["arachosia"],
        "period": {"start": -500, "end": -400, "periods": ["achaemenid"]},
        "citations": [{"source": "testauthor-2000", "evidence_level": "secondary-scholarship",
                       "relation": "supports"}],
    }
    c.update(over)
    return c


@pytest.fixture
def make(tmp_path):
    """make(claims=[...], sources=[...]) -> (errors, warnings)"""
    shutil.copytree(ROOT / "data" / "vocab", tmp_path / "vocab")
    shutil.copytree(ROOT / "data" / "geo", tmp_path / "geo")
    (tmp_path / "claims").mkdir()
    (tmp_path / "sources").mkdir()

    def _make(claims=(), sources=()):
        for kind, items in (("claims", claims), ("sources", sources)):
            for item in items:
                (tmp_path / kind / f"{item['id']}.yaml").write_text(yaml.safe_dump(item, allow_unicode=True))
        return validate(load_dataset(tmp_path))
    return _make


def rules(errors):
    return {e.split("[")[1].split()[0] for e in errors if "[" in e}


def test_good_data_passes(make):
    errors, warnings = make([good_claim()], [good_source()])
    assert errors == []
    assert warnings == []


def test_real_vocab_and_data_are_valid():
    errors, _ = validate(load_dataset())
    assert errors == []


def test_r1_missing_field(make):
    c = good_claim(); del c["statement"]
    errors, _ = make([c], [good_source()])
    assert rules(errors) == {"R1"}


def test_r2_filename_mismatch(make, tmp_path):
    make([], [good_source()])
    (tmp_path / "claims" / "wrong-name.yaml").write_text(yaml.safe_dump(good_claim()))
    errors, _ = validate(load_dataset(tmp_path))
    assert "R2" in rules(errors)


def test_r3_unknown_source_and_population(make):
    errors, _ = make([good_claim(populations=["atlanteans"],
                                 citations=[{"source": "nope", "evidence_level": "archaeology",
                                             "relation": "supports"}])], [])
    assert rules(errors) >= {"R3"}
    assert any("atlanteans" in e for e in errors)
    assert any("'nope'" in e for e in errors)


def test_r4_year_zero(make):
    errors, _ = make([good_claim(period={"start": -10, "end": 0})], [good_source()])
    assert "R4" in rules(errors)


def test_r5_unverified_needs_note(make):
    errors, _ = make([good_claim(status="unverified")], [good_source()])
    assert rules(errors) == {"R5"}


def test_r6_verified_claim_needs_verified_sources(make):
    src = good_source(verification={"status": "unverified"})
    errors, _ = make([good_claim()], [src])
    assert rules(errors) == {"R6"}


def test_r7_legend_cannot_be_strong(make):
    c = good_claim(citations=[{"source": "testauthor-2000", "evidence_level": "oral-tradition",
                               "relation": "supports"}])
    errors, _ = make([c], [good_source()])
    assert rules(errors) == {"R7"}


def test_r7_rating_without_support(make):
    c = good_claim(status="unverified", verification_note="x", strength="moderate", citations=[])
    errors, _ = make([c], [])
    assert rules(errors) == {"R7"}


def test_r7_unknown_with_no_citations_is_fine(make):
    c = good_claim(status="unverified", verification_note="UNVERIFIED — needs source check",
                   strength="unknown", citations=[])
    errors, _ = make([c], [])
    assert errors == []


def test_r8_contested_needs_a_rival(make):
    errors, _ = make([good_claim(strength="contested")], [good_source()])
    assert rules(errors) == {"R8"}


def test_r8_rival_link_from_other_side_counts(make):
    a = good_claim(id="claim-a", strength="contested")
    b = good_claim(id="claim-b", related_claims=[{"claim": "claim-a", "relation": "competes-with"}])
    errors, _ = make([a, b], [good_source()])
    assert errors == []


def test_r9_self_link(make):
    c = good_claim(related_claims=[{"claim": "test-claim", "relation": "supports"}])
    errors, _ = make([c], [good_source()])
    assert "R9" in rules(errors)


def test_r9_duplicate_doi(make):
    s1 = good_source(id="a-2000", doi="10.1234/same")
    s2 = good_source(id="b-2000", doi="10.1234/SAME")
    c = good_claim(citations=[{"source": "a-2000", "evidence_level": "archaeology", "relation": "supports"},
                              {"source": "b-2000", "evidence_level": "archaeology", "relation": "supports"}])
    errors, _ = make([c], [s1, s2])
    assert rules(errors) == {"R9"}


def test_orphan_source_warns(make):
    errors, warnings = make([], [good_source()])
    assert errors == []
    assert any("not cited" in w for w in warnings)


# ---- Cognate sets (linguistics module) ----

def good_cognate(**over):
    c = {"id": "test-set", "gloss": "test", "forms": [
        {"language": "pashto", "form": "a", "source": "testauthor-2000", "status": "unverified"},
        {"language": "avestan", "form": "b", "source": "testauthor-2000", "status": "unverified"},
    ]}
    c.update(over)
    return c


@pytest.fixture
def make_cognates(tmp_path, make):
    def _make(cognates, sources=(good_source(),)):
        d = tmp_path / "linguistics" / "cognates"
        d.mkdir(parents=True, exist_ok=True)
        for c in cognates:
            (d / f"{c['id']}.yaml").write_text(yaml.safe_dump(c, allow_unicode=True))
        return make([], list(sources))
    return _make


def test_cognate_good(make_cognates):
    errors, warnings = make_cognates([good_cognate()])
    assert errors == []
    assert not any("not cited" in w for w in warnings)  # cognates count as citing


def test_c2_unknown_language(make_cognates):
    c = good_cognate()
    c["forms"][0]["language"] = "klingon"
    errors, _ = make_cognates([c])
    assert rules(errors) == {"C2"}


def test_c3_unknown_source(make_cognates):
    c = good_cognate()
    c["forms"][1]["source"] = "made-up-1999"
    errors, _ = make_cognates([c])
    assert rules(errors) == {"C3"}


def test_c4_verified_form_needs_verified_source(make_cognates):
    c = good_cognate()
    c["forms"][0]["status"] = "verified"
    errors, _ = make_cognates([c], [good_source(verification={"status": "unverified"})])
    assert rules(errors) == {"C4"}


def test_form_without_source_fails_schema(make_cognates):
    c = good_cognate()
    del c["forms"][0]["source"]
    errors, _ = make_cognates([c])
    assert rules(errors) == {"R1"}
