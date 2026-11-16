# Free publication directory

OSRI's directory of research venues that offer free submission and a free publication route. People direct Agentic-Powered-Research, choose questions worth investigating, and assess whether the work is ready for a particular venue.

Open [the online searchable directory](https://open-source-research-initiative.github.io/venues/), [browse the verified free lists by subfield](DIRECTORY.md), or download [CSV](data/venues.csv) and [JSON](data/venues.json). The [standalone HTML file](index.html) also works locally without a server or a network connection; external source links require access to the web.

Choose a subfield and compare the recorded route, accepted contribution types, editorial demands, and source-linked metrics. Verified free routes are shown by default. Conditional waivers or funding agreements, incompletely verified leads, and paid exclusions have separate filters. Closed submissions are excluded from the default view. Preprints and repositories are available when the peer-reviewed-only filter is cleared.

Difficulty bands are provisional agent judgments within a subfield. Published acceptance rates, Journal Impact Factors, and CiteScores retain their years and source definitions. Missing data stays missing; a journal's citation impact is not a manuscript's acceptance probability. Read [the methodology](docs/methodology.md) and each venue's current instructions before submitting.

## Coverage and evidence

The first collection covers twelve clusters across Healthcare, Engineering, Informatics, Economics, Social and Behavioral Sciences, Public Policy, and cross-cutting meta-research. It is a starting collection, not an exhaustive subfield taxonomy. Initial healthcare work is nonclinical; new physical laboratory experiments are outside OSRI's initial scope.

See the [coverage table](COVERAGE.md), [retained research notes and exclusions](RESEARCH_NOTES.md), and [agent assignments](data/agent-assignments.json) for the extent and limits of this collection.

Five distinct agents work on each cluster: discovery, diamond/open dissemination expansion, fee audit, ranking evidence, and skeptical review. Retained files under [research](research/CONTRACT.md) provide the evidence trail. The [build receipt](data/build-receipt.json) reports current counts, completion, source hashes, and unresolved cross-field conflicts. Agent review is not independent human scientific review or venue endorsement.

The directory distinguishes diamond open access from a free subscription route. A subscription route can meet the zero-author-cost goal while restricting reader access. Conditions on length, article type, membership, registration, author eligibility, and AI-assisted work can still affect suitability.

## Maintain the directory

Use Python 3; no third-party libraries are required:

```bash
python3 scripts/build.py
python3 scripts/check.py
```

The build requires all sixty role files. `--allow-incomplete` is for a local research preview; a preview is not a completed directory. `scripts/check.py` verifies the evidence receipt and generated data. Edit the research records and rebuild rather than editing generated files.

The canonical files are [venues.json](data/venues.json) for deduplicated venues and [memberships.json](data/memberships.json) for each venue's independently reviewed subfield listing. Keep subfield-specific difficulty judgments separate. Conflicting fee audits are conservatively placed in `needs_verification` until an evidenced correction resolves them.

To add or correct a venue, retain the official policy URL, access date and limitations, article-type conditions, all mandatory costs, and the source for peer-review status. Keep metrics with their exact year or period and denominator. Record unavailable evidence and material policy changes. Use [CONTRIBUTING.md](CONTRIBUTING.md) for the review workflow.

The [OSRI website](https://open-source-research-initiative.github.io/venues/) publishes a snapshot pinned to this repository's source commit. After reviewing and committing a directory update, export it to an OSRI hub checkout with `python3 scripts/export_hub.py /path/to/osri`; publish the hub change through its review and deployment workflow. The catalog checks run on pushes and pull requests here.

Original guides and catalog compilations use CC BY 4.0; original code uses MIT. [Third-party terms remain separate](LICENSE.md).
