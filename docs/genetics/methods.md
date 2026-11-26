---
title: Reading the methods
order: 3
---

# Reading the methods: PCA, f-statistics and qpAdm

Ancient-DNA papers use a small set of methods again and again. You don't need
the maths to read them well, but you do need to know what each method answers,
and what it doesn't.

## PCA (principal component analysis)

**What it does.** Each person's DNA is a list of hundreds of thousands of
positions. PCA squeezes that into a few numbers, usually two, so people can be
plotted as dots on a chart. People who share more ancestry tend to sit closer
together. The method and the standard software (EIGENSOFT's `smartpca`) were
described by Patterson and colleagues [@patterson-2006].

**How ancient DNA is usually shown.** Ancient samples have lots of missing
positions, so papers typically compute the axes from present-day people and
then **project** the ancient individuals onto that map. The map's shape is
decided by the present-day samples chosen.

**What it's good for:**
- A quick overview of which groups are similar.
- Spotting outliers, such as someone buried at a site whose ancestry differs
  from their neighbours.
- Seeing *clines*: gradients where ancestry shifts gradually across a region.

**Where it misleads:**
- **The picture depends on who's included.** Add or remove populations and the
  axes change. A group with many samples can pull an axis towards itself
  [@mcvean-2009].
- **"In between" doesn't prove "mixed".** A dot halfway between two clusters
  *might* be a mixture of the two, or it might have its own separate history.
  PCA can't tell the difference [@mcvean-2009].
- **Two dimensions hide a lot.** Groups that overlap on a 2-D chart can differ
  on the axes that aren't shown.
- **Distance on the chart is not time.** It's not a family tree and doesn't
  show who came first.

**How to read a PCA claim:** treat it as a *hypothesis generator*. "These
samples look intermediate" is a reason to run a formal test, not a conclusion.

## f-statistics (f3, f4, D)

**What they do.** These are formal tests that compare how much genetic drift
(random change over generations) groups share [@patterson-2012]. Two examples:

- **f3 admixture test:** "Is population C a mix of something like A and
  something like B?" A clearly negative result is strong evidence of mixture.
  A non-negative result doesn't rule mixture out.
- **f4 / D-statistic:** "Is X closer to Y than to Z, compared with an
  outgroup?" This tests a specific tree shape, and the result is a number
  with an uncertainty.

These are the building blocks of qpAdm.

## qpAdm

**What it does.** qpAdm tests whether a **target** population (say, a set of
Iron Age individuals) can be modelled as a mix of a few **source** populations
(say, a Bronze Age steppe group and a BMAC group). The test works by checking
the target against a fixed set of other **reference** populations. It was
introduced in the supplementary materials of a 2015 study of steppe migration
into Europe [@haak-2015].

**What it outputs:**
- **Proportions:** for example "65% source A + 35% source B", each with a
  standard error.
- **A p-value:** roughly, whether the model is *consistent* with the data. By
  convention, a p-value above about 0.01–0.05 means the model is "not rejected".

**The four most important cautions:**

1. **"Not rejected" is not "proven".** Often several different models fit the
   same target. A careful paper reports all the models it tried, including the
   ones that failed [@harney-2021].
2. **Sources are stand-ins.** "Steppe_MLBA" in a model means "a population
   genetically like these sampled steppe individuals". It doesn't mean the
   target descends from those exact people.
3. **Results depend on the reference set.** Choosing the reference populations
   is a judgement call. Different reasonable choices can give different answers
   [@harney-2021].
4. **Complex models are hard to pin down.** With many sources or many mixing
   events, very different histories can fit the same statistics equally well
   [@maier-2023].

**How to read a qpAdm claim:** look for (a) the p-value, (b) the standard errors
on the proportions, (c) whether alternative models were tested, and (d) how
many individuals are in the target and in each source.

## Y-chromosome and mitochondrial haplogroups

Popular discussions of Pashtun origins often focus on haplogroups, such as a
particular Y-chromosome lineage being common. Keep in mind:

- A Y-chromosome is **one line of ancestry**: father's father's father…
  Mitochondrial DNA is likewise one line: mother's mother's mother… Going back
  a thousand years, a person has many thousands of ancestor slots, and these
  lines cover only two of them.
- A haplogroup can be common in several unrelated populations, and its age
  and place of origin are often estimated with wide uncertainty.
- Whole-genome methods like PCA and qpAdm look at all ancestors at once, which
  is why recent studies rely on them for questions about population history.

## What genetics cannot tell us

- **What language people spoke.** A population can adopt a new language with
  little genetic change, or keep its language through heavy mixture.
- **What people called themselves,** or which ethnic group they belonged to.
- **Whether a legend is true in its details.** At most, genetics can say
  whether a large ancestry contribution from a particular *source region* fits
  the data, and only if suitable samples exist.

This is why the atlas keeps genetic, linguistic, archaeological and textual
evidence side by side, each labelled for what it can and can't show.
