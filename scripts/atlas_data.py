"""Load the atlas data files into Python objects.

Shared by validate.py now, and by build_site.py later, so both see the
data in exactly the same way.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCHEMA_DIR = ROOT / "schema"

VOCAB_NAMES = ("evidence-levels", "populations", "regions", "periods", "languages")
GUIDE_NAMES = ("questions", "glossary")   # data/guides/: plain-language content for the site


def _stringify_dates(value):
    """YAML turns `2026-11-25` into a date object; JSON Schema expects a string."""
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _stringify_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify_dates(v) for v in value]
    return value


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return _stringify_dates(yaml.safe_load(f))


@dataclass
class Record:
    """One loaded file: its data plus where it came from (for error messages)."""
    data: dict
    path: Path


@dataclass
class Doc:
    """A Markdown page in docs/: front matter (title, order) plus the body text."""
    path: Path
    meta: dict
    body: str


def load_doc(path: Path) -> Doc:
    text = path.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            meta = yaml.safe_load(text[4:end]) or {}
            text = text[end + 4:].lstrip("\n")
    return Doc(path, meta, text)


@dataclass
class Dataset:
    data_dir: Path = DATA_DIR
    vocab: dict[str, list[dict]] = field(default_factory=dict)   # name -> list of entries
    claims: list[Record] = field(default_factory=list)
    sources: list[Record] = field(default_factory=list)
    cognates: list[Record] = field(default_factory=list)                # data/linguistics/cognates/
    guides: dict[str, list[dict]] = field(default_factory=dict)        # data/guides/*.yaml
    docs: list[Doc] = field(default_factory=list)                 # docs/**/*.md
    load_errors: list[str] = field(default_factory=list)          # files that aren't valid YAML

    def vocab_ids(self, name: str) -> set[str]:
        return {e.get("id") for e in self.vocab.get(name, []) if isinstance(e, dict)}

    def vocab_by_id(self, name: str) -> dict[str, dict]:
        return {e["id"]: e for e in self.vocab.get(name, []) if isinstance(e, dict) and "id" in e}


def _load_dir(directory: Path, ds: Dataset) -> list[Record]:
    records = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = load_yaml(path)
        except yaml.YAMLError as e:
            ds.load_errors.append(f"{path}: not valid YAML: {e}")
            continue
        records.append(Record(data, path))
    return records


def load_dataset(data_dir: Path = DATA_DIR, docs_dir: Path | None = None) -> Dataset:
    ds = Dataset(data_dir=data_dir)
    docs_dir = docs_dir or data_dir.parent / "docs"
    for path in sorted(docs_dir.glob("**/*.md")) if docs_dir.is_dir() else []:
        try:
            ds.docs.append(load_doc(path))
        except yaml.YAMLError as e:
            ds.load_errors.append(f"{path}: front matter is not valid YAML: {e}")
    for name in VOCAB_NAMES:
        path = data_dir / "vocab" / f"{name}.yaml"
        try:
            ds.vocab[name] = load_yaml(path) or []
        except (OSError, yaml.YAMLError) as e:
            ds.load_errors.append(f"{path}: {e}")
            ds.vocab[name] = []
    ds.claims = _load_dir(data_dir / "claims", ds)
    ds.sources = _load_dir(data_dir / "sources", ds)
    ds.cognates = _load_dir(data_dir / "linguistics" / "cognates", ds)
    for name in GUIDE_NAMES:
        path = data_dir / "guides" / f"{name}.yaml"
        try:
            ds.guides[name] = (load_yaml(path) or []) if path.exists() else []
        except yaml.YAMLError as e:
            ds.load_errors.append(f"{path}: {e}")
            ds.guides[name] = []
    return ds
