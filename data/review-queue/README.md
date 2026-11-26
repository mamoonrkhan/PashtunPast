# Review queue

`scripts/discover_sources.py` searches open scholarly APIs for possible sources and
puts what it finds in [`queue.yaml`](queue.yaml). **Nothing here is a source yet.**
A person has to look at each candidate first.

## Reviewing a candidate

1. Open the DOI or link. Is it real? Is it actually about our topics?
2. If it's useful, write `summary:` in **your own words** (2–3 sentences: what the work is
   and why it matters here). Don't paste the abstract; abstracts are usually copyrighted.
3. Set `status: approved`, or `status: rejected` with a short `reviewer_note` saying why.
4. Run:

   ```
   python scripts/discover_sources.py promote
   python scripts/validate.py
   ```

   Approved entries become files in `data/sources/`, marked **unverified**. A source only
   becomes verified when someone has checked its details and the passages a claim cites.

Rejected entries stay in the queue so the script doesn't suggest them again.

## Running a search

```
python scripts/discover_sources.py search                 # every query, every service
python scripts/discover_sources.py search --dry-run       # print only
python scripts/discover_sources.py search --apis openalex,crossref --since 2018 --limit 5
```

Searches live in [`queries.yaml`](queries.yaml). Each has `require` words (the title must
contain one) and the file has `exclude` words (e.g. medical terms), to keep the queue short.

Optional environment variables:

| Variable | Effect |
|---|---|
| `DISCOVERY_CONTACT_EMAIL` | Sent to Crossref and OpenAlex as `mailto`, which gets faster service. Only set this if you're happy to share that address with them. |
| `GITHUB_TOKEN` | Raises GitHub's search limit from 10 to 30 requests a minute. |

## What the script does and doesn't do

| Service | What it finds | Status |
|---|---|---|
| Crossref | Journal articles, books, chapters with DOIs | Used |
| OpenAlex | Broad scholarly index, including many arXiv and bioRxiv records | Used |
| Europe PMC | Preprints (bioRxiv, medRxiv…). bioRxiv's own API has no keyword search. | Used; its robots.txt asks for 10 s between requests, and we wait that long |
| arXiv | Physics, CS and quantitative biology preprints | **Skipped**: `export.arxiv.org/robots.txt` disallows all paths. Many arXiv papers still arrive through OpenAlex. |
| GitHub | Code and datasets (only for queries that list `github`) | Used |

* **Metadata only:** title, authors (first five), year, venue, DOI, link. No abstracts, no full text.
* **robots.txt** is checked on every host (RFC 9309): no file means allowed; a server error means
  "assume disallowed".
* **Rate limits:** at least 1 s between requests to the same host (3 s for arXiv, 6.5 s for GitHub
  without a token), longer if the host's robots.txt asks; 429/503 responses are retried after the
  wait the server requests.
* The User-Agent names the project and contains no personal details.
