# Pashtun Origins Project

**An open, evidence-first research atlas of Pashtun history, language and ancestry.**

Where do the Pashtuns and the Pashto language come from? People have proposed
many answers:
- the Paktyes named by Herodotus
- Eastern Iranian speakers related to the Saka and Scythians
- the peoples of ancient Bactria
- Bronze Age migrants from the steppe
- the Lost Tribes of Israel, as told in Pashtun genealogical tradition

These ideas get mixed together, often with more confidence than the evidence allows.

This project lays out the evidence **claim by claim**:
- **every statement is cited** and labelled by **what kind of evidence** supports it and **how strong** that evidence is
- **competing explanations sit side by side**, so readers can weigh them for themselves

It is community-driven, non-nationalist, and open to correction.

> **Status: Version 1, early.** Every entry is currently marked **UNVERIFIED**.
> The sources exist (DOIs and catalogue records were checked), but no person
> has yet confirmed each cited passage. Helping verify them is the most
> valuable contribution right now. See [Contributing](#contributing).

---

## What's in the atlas

| Section | What you'll find |
|---|---|
| **Explore** | Every claim as a card, searchable and filterable by population, period, evidence type, strength and topic |
| **Claim pages** | The statement, its citations grouped as supporting / contradicting / context, and competing claims shown side by side |
| **Timeline** | Claims placed in time, from the Bronze Age to the present |
| **Map** | Regions such as Bactria, Arachosia and Gandhara, shaded by how many claims concern them |
| **Languages** | Pashto compared with Avestan, Old Persian, Khotanese Saka and Bactrian, with each word cited to a dictionary |
| **Genetics** | Plain-language guides to the Allen Ancient DNA Resource, PCA and qpAdm, and the plan for Version 2 |
| **Sources** | Every cited work, its verification status, and which claims use it |

The seed data covers:
- Pashto's place among the Eastern Iranian languages
- Herodotus and the Paktyes
- the Saka and Scythians
- Bactria and the BMAC
- Andronovo and steppe ancestry
- the Kushan period
- the Lost Tribes tradition

## Method

### Claims, not conclusions

The atlas is built from **claims**: single statements worded as precisely as
the evidence allows. A claim about what a text says is kept separate from a
claim about whether it's true.

For example, *"Herodotus names a people called the Paktyes"* is one claim, and
*"the Paktyes were ancestors of the Pashtuns"* is another. They're linked,
but rated separately.

### Evidence types

Each citation is labelled with the **kind** of evidence it provides. These are
types, not a ranking: DNA can't tell us what language someone spoke, and a
dictionary can't tell us anyone's ancestry.

| Code | Evidence type | Highest strength it can support on its own |
|---|---|---|
| GEN | Peer-reviewed genetics | strong |
| LING | Linguistic consensus | strong |
| ARCH | Archaeology | strong |
| TEXT | Primary historical text | strong |
| SCHOL | Secondary scholarship | strong |
| ORAL | Oral tradition / legend | moderate |
| SPEC | Speculative / disputed | weak |

### Strength

Each claim is rated **strong**, **moderate**, **weak**, **contested** (serious
evidence on more than one side) or **unknown** (not yet assessed), always for
the statement *as worded*.

### Verification

A claim is **verified** only when a person has checked that every cited source
says what the claim says. Until then it's shown as **UNVERIFIED — needs source
check**, with a note on what to check.

### Enforced automatically

These rules aren't just guidelines. A validator runs on every pull request and
blocks merging if, for example:
- a claim cites a source that doesn't exist
- a strength is rated higher than its evidence allows (a legend alone can't make a claim "strong")
- a "contested" claim doesn't link the claim it's contested with

### Groups are labelled by kind

"BMAC" is an **archaeological culture**, "Steppe_MLBA" a **genetic cluster**,
"Saka" a **name used for peoples**, and "Kushan" a **state**. Confusing these
kinds of groups is one of the most common errors in origin debates, so every
population in the atlas says which kind it is.

## Quick start

Requirements: Python 3.11+ and git.

```bash
git clone https://github.com/mamoonrkhan/PashtunPast.git
cd PashtunPast
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/validate.py         # check all data against the rules
python -m pytest -q                # run the tests
python scripts/build_site.py       # build the website into _site/
python -m http.server -d _site 8000   # open http://localhost:8000
```

Other tools:

```bash
python scripts/validate.py --check-dois                      # confirm DOIs on Crossref
python scripts/discover_sources.py search --dry-run          # look for new candidate sources
python scripts/discover_sources.py promote                   # add approved candidates as sources
```

## How the repository is organised

```
data/                  The research itself: plain-text YAML files, one per entry
  claims/              Claims, each with citations, strength and links to rival claims
  sources/             Bibliographic records (metadata and own-words summaries only)
  vocab/               Fixed lists: evidence levels, populations, regions, periods, languages
  linguistics/cognates/  Word comparisons across Iranian languages
  geo/                 Rough map shapes for historical regions
  review-queue/        Candidate sources found by the discovery script, awaiting review
docs/genetics/         Explainers on ancient DNA and the Version 2 analysis plan
docs/design/           Design notes for future versions
schema/                Machine-checkable rules for each kind of data file
scripts/               validate.py, build_site.py, discover_sources.py
site/                  Website templates, CSS and JavaScript (no framework)
templates/             Copy-and-fill files for new claims, sources and word sets
tests/                 Automated tests
.github/               Checks and deployment, pull-request template, issue forms
```

The website is generated entirely from `data/` and `docs/`. To change what the
site says, change the data, never the HTML.

## Contributing

You don't need to code. The most valuable things to do right now:

1. **Verify an entry.** Pick a claim, open its sources, find the cited passage,
   and record what you checked.
2. **Review candidate sources** in [`data/review-queue/`](data/review-queue/README.md).
3. **Check word forms** in the cognate table against the cited dictionaries.
4. **Suggest a source** or **report an error** using the issue forms.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) (the sourcing rules and
step-by-step instructions) and the [Code of Conduct](CODE_OF_CONDUCT.md).
In short:
- never cite what you haven't read
- label the evidence honestly
- word claims no more strongly than the evidence allows
- describe views you disagree with fairly

## Deploying

The site is static and deploys free to GitHub Pages. On every push to `main`, a
GitHub Actions workflow validates the data, runs the tests, builds the site
and, once switched on, publishes it.

To switch publishing on (GitHub Pages needs a public repository on a free plan):
1. **Settings → Pages → Source: GitHub Actions**
2. **Settings → Secrets and variables → Actions → Variables:** add `DEPLOY_PAGES` = `true`

Until then, the deploy step is skipped and only the checks run.

To require review and passing checks before merging, add a branch protection
rule for `main`.

## Roadmap

### Version 1 (current)
- [x] Data model with validation rules for claims, sources and vocabularies
- [x] 15 seed claims and 24 sources, all marked unverified
- [x] Static website: explore, claim pages, timeline, map, sources, method
- [x] Linguistics module: 9 cognate sets across 5 languages
- [x] Source discovery script with a human review queue
- [x] Genetics documentation and a pre-registered analysis plan
- [x] Contribution guide, code of conduct, pull-request template, issue forms
- [ ] **Verify the seed data** (claims, sources, page numbers, word forms)
- [ ] Review the first batch of candidate sources
- [ ] Publish the site

### Version 2 (designed, not built)
See [docs/design/v2.md](docs/design/v2.md).
- PCA visualisation of open ancient-genome data from the AADR (present-day South and
  Central Asian samples alongside ancient Steppe, BMAC and Saka/Scythian samples),
  following the [pre-registered plan](docs/genetics/v2-analysis-plan.md)
- An etymological database with documented sound changes
- A contributor and moderation workflow built on GitHub
- A citation-graph view showing how claims, sources and evidence connect

### Later ideas
- Pashto (right-to-left) and other translations of the interface
- More periods: Hephthalites, early Islamic sources, and the first Pashto literature

## Licences

- **Code:** [MIT](LICENSE)
- **Data and writing:** [CC BY-SA 4.0](LICENSE-DATA.md)
- Cited works remain under their own copyright. The atlas stores only
  bibliographic details, links and summaries in its own words.

## Acknowledgements

The atlas relies on open infrastructure:
- **Crossref, OpenAlex, DataCite and Europe PMC** for bibliographic metadata
- the **Perseus Digital Library** for classical texts
- **OpenStreetMap** and **Leaflet** for the map
- the **Allen Ancient DNA Resource** for the genetic data planned for Version 2

Above all, it relies on the researchers whose fieldwork, lab work and
scholarship it cites.
