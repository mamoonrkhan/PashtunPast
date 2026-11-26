---
title: The Allen Ancient DNA Resource (AADR)
order: 2
---

# The Allen Ancient DNA Resource (AADR)

## What it is

The AADR is a free, curated collection of genetic data from **already
published** studies. It is maintained by David Reich's laboratory at Harvard
Medical School and described in a 2024 paper [@mallick-2024]. The files are
downloadable from Harvard Dataverse [@aadr-dataset].

It solves a practical problem. Each ancient-DNA paper releases its data in its
own way. The AADR gathers thousands of these ancient individuals, plus many
present-day people from published studies, and puts them all in one format
with one consistent set of genetic positions. That makes it possible to
compare an Iron Age Saka burial with a Bronze Age BMAC site and a present-day
population in a single analysis.

## What's inside

A release contains, roughly:

| File | What it holds |
|---|---|
| Genotypes (`.geno`) | For each person, their genetic variant at each of a fixed list of positions |
| SNP list (`.snp`) | The positions ("SNPs") on the genome that were measured |
| Individual list (`.ind`) | Each person's ID, sex and group label |
| Annotation table (`.anno`) | Date, location, publication, data quality and other notes for each individual |

These files use the EIGENSTRAT family of formats, read by the EIGENSOFT and
ADMIXTOOLS software. They come in two main versions, named after the set of
positions measured:

- **1240k:** about 1.2 million positions. Used for most ancient samples.
- **HO (Human Origins):** about 600,000 positions, overlapping with a genotyping
  array used for many present-day populations. **This is the version that
  lets ancient and modern people be compared directly.**

The exact counts of individuals and positions change with each release. The
2024 paper and each release's README give the numbers [@mallick-2024].

## Reading the annotation table

The `.anno` table is where most of the useful context lives. For each
individual it records things like:

- **Date:** either from radiocarbon dating or estimated from the archaeological
  context. These are not the same quality, and the table says which.
- **Location:** site, country and coordinates.
- **Publication:** which paper first reported the data. This is what we cite.
- **Data quality:** how many positions were actually read. Ancient DNA is
  degraded, so some individuals have only a small fraction of positions measured.
- **Group label:** a name for the analysis group, usually built from place,
  site and period. Extra tags mark special cases, for example individuals who
  are genetic outliers compared with others from the same site.
- **Assessment notes:** warnings about contamination, close relatives, or
  other problems.

**Group labels are researchers' tools, not ethnic names.** A label made from a
site and period name describes *where and when* people were buried. It doesn't
describe *who they were*.

## Using it responsibly

- **Cite the original papers,** not just the AADR. Every sample came from
  someone else's fieldwork and lab work.
- **Record the release.** Different releases contain different samples and
  corrections. Any analysis must state which release it used and record file
  checksums (fingerprints that prove which files were used).
- **Check the terms.** Read the README of the release you download. Some
  present-day datasets come with conditions on how they may be used.
- **Don't re-upload the data** into this repository. It is large and has its
  own terms. Our scripts will download it from the official source instead.
- **Present-day samples are real communities.** Some present-day groups in the
  dataset come from the region this project studies. They should be described
  using the labels and context of the studies that collected them, and never
  ranked or judged.
