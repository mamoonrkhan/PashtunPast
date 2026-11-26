---
title: Version 2 analysis plan
order: 4
---

# Version 2 analysis plan

**Status:** plan only. Nothing here has been run.

**Why write the plan first?** If you decide your methods after seeing results,
it's easy, even unintentionally, to keep tweaking until the picture matches
what you hoped to see. Writing down what we'll do, and what would count as a
surprising result, *before* running anything protects the project from that.
This is sometimes called **pre-registration**. Any change to the plan after we
start will be recorded in the changelog at the end, with the reason.

## 1. Goal

Reproduce, with open data and open code, the broad patterns that published
studies report for South and Central Asia. Then show them interactively on the
site. Specifically:

1. A **PCA** that places published **present-day** South and Central Asian
   samples next to **ancient** Steppe (Bronze Age), BMAC and Saka/Scythian-related
   samples, using the method in published work [@patterson-2006].
2. Optionally, after the PCA is reviewed: **qpAdm replications** of models
   already published (for example in [@narasimhan-2019]). The aim is to check
   that we can reproduce them, not to propose new ancestry claims.

**Not a goal:** finding a "Pashtun origin" with genetics alone. See
[Reading the methods](methods.md) for why that isn't possible.

## 2. Data

| Item | Decision |
|---|---|
| Dataset | AADR [@aadr-dataset], **HO** version, so ancient and present-day individuals share positions |
| Release | The current release when work starts; release number and file checksums recorded in `analysis/genetics/DATA.md` |
| Terms | Read and record the release README's usage conditions before any analysis |
| Storage | Data is downloaded by script into a git-ignored folder, never committed |
| Personal data | None. Only individuals from published studies, as distributed in the AADR |

### Which individuals

Groups are chosen from the `.anno` table by **published group label**, and the
list is written down here *before* plotting. Candidate groups (exact labels to be
filled in from the release):

- **Present-day:** published South and Central Asian groups in the HO data,
  including any group labelled Pathan/Pashtun (the Human Genome Diversity
  Project is expected to include a "Pathan" group from Pakistan; to be confirmed
  in the `.anno` table), Tajik, Burusho, Kalash, Baloch, Brahui, Sindhi, Punjabi
  and others, plus Iranian and other West Eurasian reference groups.
- **Ancient:**
  - Bronze Age steppe (Sintashta/Andronovo-associated)
  - BMAC sites (e.g. Gonur)
  - Iron Age Saka/Scythian-related groups
  - Bronze and Iron Age Swat Valley
  - Iranian and Turanian farmers

  These are the groups analysed in [@narasimhan-2019], [@damgaard-2018] and
  [@unterlander-2017].

### Quality filters (fixed in advance)

- Exclude ancient individuals with fewer than **30,000** positions covered.
  This is a common threshold; the exact value will be recorded and tested in the
  sensitivity checks.
- Exclude individuals the `.anno` table flags as contaminated, as duplicates,
  or (keeping one of each pair) as close relatives.
- Keep individuals tagged as outliers, but **mark them** on the plot. Don't
  silently drop them.

## 3. Method

1. **Download and verify:** a script downloads the release and checks its
   checksums.
2. **Select:** a script reads the `.anno` table and writes the list of chosen
   individuals with the reason for each exclusion.
3. **PCA:** run EIGENSOFT `smartpca` [@patterson-2006]:
   - compute the axes from **present-day** West and South Eurasian samples
   - **project** the ancient samples onto them (`lsqproject: YES`), as published
     studies do
4. **Export:** save each individual's first four PC coordinates, together with
   their group, date, place and original publication, to a small JSON file
   for the site.
5. **Sensitivity checks:** repeat with (a) a different set of present-day
   samples defining the axes, and (b) a stricter quality threshold. Report
   whether the picture changes. If it does, show both versions.
6. **Sanity check:** compare our plot with the corresponding published figure
   in [@narasimhan-2019]. If they differ substantially, we stop and find out why
   before publishing anything.

If qpAdm replication goes ahead: use ADMIXTOOLS 2 [@maier-2023], and use the
**same** target, source and reference populations as the published model.
Report every model tested, with p-values, proportions and standard errors,
following the cautions in [@harney-2021].

## 4. How results enter the atlas

Our own analysis is **not peer-reviewed**, so it can't use the
`peer-reviewed-genetics` evidence level. V2 will add a new evidence level:

| id | label | max strength |
|---|---|---|
| `project-analysis` | Project analysis (not peer reviewed) | moderate |

A project-analysis citation can **support or challenge** a claim, but never be
the only reason a claim is rated strong. Every such claim will link to the
code, data release and parameters used.

## 5. The website view

- An interactive scatter plot: dots coloured by group, ancient samples marked
  differently from present-day ones, hover to see group, date, site and source
  paper.
- Filters by period and region, sharing the atlas's existing filter bar.
- A permanent note above the plot: *"PCA shows genetic similarity, not identity
  or language. Positions depend on which samples are included."* Plus a link to
  the methods page.
- A toggle between the main analysis and the sensitivity-check versions.

## 6. Reproducibility

- All code in `analysis/genetics/`, runnable with one command (a `Makefile`).
- Software versions pinned in an environment file (EIGENSOFT and ADMIXTOOLS 2
  versions recorded).
- The heavy computation runs locally, not in GitHub Actions. Its small outputs
  (JSON coordinates and logs) are committed, along with the data release
  number and checksums, so anyone can re-run and compare.

## 7. Ethics and boundaries

- **Only published, openly distributed data,** used within its stated terms.
- **No personal or consumer genetic data,** and no claims about living individuals.
- **Present-day groups are described with their published labels and context.**
  No ranking, no "purity" language.
- **Results are presented as ancestry *proportions from modelled sources*,**
  never as statements about who belongs to which people.
- **Results that contradict popular beliefs,** including beliefs held within the
  community, are reported plainly but respectfully, next to the evidence for
  other views.

## 8. Decisions still open

- Which exact AADR release, and whether its terms allow publishing derived
  per-individual PC coordinates on the site (if not, show group averages only).
- The exact present-day groups that define the PCA axes.
- Whether to include the 1240k data for a second, ancient-only analysis.
- Who reviews the analysis before publication. Ideally, someone with
  population-genetics experience outside the core team.

## Changelog

- *2026-11-25:* plan written (V1). Nothing run.
