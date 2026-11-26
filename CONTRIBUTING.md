# Contributing to the Pashtun Origins Project

Thank you for helping. This project is an **evidence-first** atlas: its value
comes entirely from how carefully each statement is sourced and labelled. You
don't need to be a programmer to contribute. Most contributions are edits to
small, plain-text YAML files, and you can make them in GitHub's web editor.

Please also read the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## The sourcing rules

These rules are the heart of the project. Many are also checked automatically
by `scripts/validate.py`, so a pull request that breaks them can't be merged.

### 1. Never invent a source

- Only cite a work you have **opened yourself**, and only for what it **actually
  says**. If you remember "someone showed X" but can't find where, don't cite
  anyone. Mark the claim `unverified` and say what's missing in
  `verification_note`.
- **AI tools often invent convincing citations,** with real-looking authors,
  titles and DOIs. If you used one, check every reference against the original
  publication before submitting.
- A DOI that resolves is not enough. The work must also say what you cite it for.

### 2. Cite the exact place

Give a `locator`: page, chapter, figure, table, verse or dictionary headword
(for example `Histories 7.67`, `pp. 112–115`, `Fig. 3`, `s.v. plār`). A
reviewer must be able to find the passage in a few minutes.

### 3. Label the evidence type honestly

Choose the evidence level for **what the source is**, not how much you trust
it:

| Level | Use for | Not for |
|---|---|---|
| `peer-reviewed-genetics` | DNA studies in peer-reviewed journals | Preprints (use `secondary-scholarship` or `speculative` until published) |
| `linguistic-consensus` | Conclusions standard in historical linguistics, as stated in reference works | One scholar's new proposal (use `secondary-scholarship`) |
| `archaeology` | Excavation reports and archaeological syntheses | Claims about language or ethnicity drawn from objects alone |
| `primary-historical-text` | Ancient or medieval texts and inscriptions, cited by passage | Modern retellings of them |
| `secondary-scholarship` | Modern scholarly books and articles interpreting evidence | |
| `oral-tradition` | Genealogies, legends, community histories | Treating a tradition as proof of an event |
| `speculative` | Fringe or rejected hypotheses, listed so readers can see them | |

**These are types, not a ranking.** DNA can't tell you what language someone
spoke, and a dictionary can't tell you anyone's ancestry.

### 4. Word claims precisely

A claim's strength is judged against its **exact wording**. Keep "a text says
X" separate from "X is true":

- ✅ *Herodotus names a people called the Paktyes.* A claim about a text; can be strong.
- ✅ *The Paktyes were ancestors of the Pashtuns.* A separate historical claim; currently contested.
- ❌ *Herodotus proves the Pashtuns have lived here for 2,500 years.* Mixes both and overstates.

Don't confuse kinds of groups. An **archaeological culture** (BMAC, Andronovo),
a **genetic cluster** (Steppe_MLBA), a **language group** and an **ethnic
name** are different things. `data/vocab/populations.yaml` records which is which.

### 5. Strength must match the evidence

| Strength | Meaning |
|---|---|
| `strong` | Well supported by the cited evidence, for the statement as worded |
| `moderate` | Supported, with real gaps or caveats |
| `weak` | Thin support |
| `contested` | Serious evidence or arguments on more than one side. Must link the rival claim or a contradicting source. |
| `unknown` | Not yet assessed. Required when there are no supporting citations. |

Oral tradition alone can support at most `moderate`, and speculation at most
`weak`. The validator enforces this.

### 6. Present competing views fairly

If scholars disagree, add the rival view as its own claim and link the two
with `competes-with` or `contradicts`. Write each side the way its best-informed
supporters would put it. The aim is that a reader can't tell which side the
author of the entry personally prefers.

### 7. Don't copy copyrighted text

Store **metadata, links and summaries in your own words** (at most 600
characters). Don't paste abstracts or passages. If exact wording truly matters,
for example a translated line of an inscription, quote at most one sentence
and give the locator.

### 8. Verification means a person checked

Set `status: verified` only after **you** opened the source and confirmed it
says what we cite it for. Record who and when:

```yaml
verification:
  status: verified
  checked_by: your-github-username
  checked_on: 2026-01-15
  notes: Read pp. 112–115; the table on p. 114 gives the figures cited.
```

A claim can only be verified once every source it cites is verified (rule R6).

### 9. Sensitive material

- No personal or consumer genetic data, and nothing about identifiable living
  people.
- No rankings of tribes, clans or ethnic groups, and no "purity" language.
- Present-day communities are described with the labels and context used by
  the studies that collected the data.

---

## How to contribute

### Option A: in the browser (no installation)

1. Open the file you want to change on GitHub (or a template in `templates/`),
   then click the pencil icon.
2. Make your change. GitHub creates a copy (a "fork") and a branch for you.
3. Click **Propose changes**, then **Create pull request**, and fill in the template.
4. The automatic checks run within a few minutes. If they fail, click
   **Details** to see the error message, which says what to fix.

### Option B: on your computer

```bash
git clone <your fork's URL>
cd pashtun-origins
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

git checkout -b add-claim-sogdian-loanwords
# … edit files …
python scripts/validate.py          # data rules
python -m pytest -q                 # tests
python scripts/build_site.py        # build the site
python -m http.server -d _site 8000 # preview at http://localhost:8000
```

Then push your branch and open a pull request.

---

## Common tasks

### Add a source

1. Copy `templates/source.yaml` to `data/sources/<familyname-year>.yaml`.
2. Fill in the exact title, authors, year, venue and a DOI, URL or ISBN if one exists.
3. Write a 2–3 sentence summary in your own words.
4. Leave `verification.status: unverified` unless you've checked it fully.
5. Optional: `python scripts/validate.py --check-dois` asks Crossref whether the DOI
   exists and shows its registered title for comparison.

### Add a claim

1. Copy `templates/claim.yaml` to `data/claims/<short-id>.yaml`. The file name must
   equal the `id`.
2. Write the `statement` precisely (rule 4).
3. Add `citations`: each one names a `source`, an `evidence_level`, a `relation`
   (`supports`, `contradicts` or `context`) and a `locator`.
4. Choose `populations`, `regions` and `period.periods` from the lists in
   `data/vocab/`. If one is missing, add it there in the same pull request.
5. Set `strength` (rule 5). Link related or competing claims under `related_claims`.
   You only need to add the link on one side; the site shows it on both.

### Add or check a word in the cognate table

1. Copy `templates/cognate.yaml`, or edit a file in `data/linguistics/cognates/`.
2. Each form needs a `source` (a dictionary) and a `locator` (page and headword).
3. Leave a language out rather than guess. An empty cell is honest.
4. To verify an existing form, look it up, correct the locator, and set `status: verified`.

### Review the source queue

See [`data/review-queue/README.md`](data/review-queue/README.md). Open each
candidate, write a summary in your own words, approve or reject it, then run
`python scripts/discover_sources.py promote`.

### Improve the website or scripts

Code lives in `scripts/` (Python) and `site/` (templates, CSS and plain
JavaScript). Add or update tests in `tests/` for any change in behaviour.
Insert user-supplied text with `textContent` (JavaScript) or Jinja's automatic
escaping (templates), never as raw HTML.

---

## What reviewers check

- Every new or changed citation: does the source exist, and does the cited
  passage say this?
- Is the evidence level right for the kind of source?
- Is the statement worded no more strongly than the evidence allows?
- Are competing views linked and fairly described?
- No copied text; summaries are in the contributor's own words.
- The automatic checks pass.

Changes to `data/` need **at least one approving review** from someone other
than the author.

## Disagreements

Disagree with evidence, not with people. If you think a claim is wrong:

1. Open an issue with the **Report an error** form, citing your sources.
2. If both positions have serious support, the outcome is usually **two linked
   claims** marked `contested`, not a winner.
3. Maintainers decide based on the sourcing rules above, not on who argues longest.

## Licensing of contributions

By submitting a contribution, you agree that it is licensed under the project's
licences:

- **Code** (`scripts/`, `site/`, `tests/`, workflows): [MIT](LICENSE)
- **Data and writing** (`data/`, `docs/`, Markdown files): [CC BY-SA 4.0](LICENSE-DATA.md)

Only contribute material you have the right to share under these terms.

## Quick reference: automatic checks

| Rule | What it checks |
|---|---|
| R1 | File matches its schema (required fields, allowed values) |
| R2 | IDs are unique and match file names |
| R3 | Every referenced source, population, region, period, claim and map file exists |
| R4 | Dates make sense (start ≤ end, no year 0) |
| R5 | Unverified claims explain what needs checking |
| R6 | Verified claims cite only verified sources |
| R7 | Strength doesn't exceed what the evidence types allow |
| R8 | Contested claims link a rival claim or contradicting source |
| R9 | No self-links; no duplicate DOIs |
| C1–C4 | Cognate sets: schema, known languages, existing sources, verified forms use verified sources |
| D1 | Citations in docs (`[@source-id]`) point to existing sources |
