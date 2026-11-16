# Free publication directory

OSRI's directory helps people find research venues with a free author route and an evidenced policy compatible with substantive AI-assisted research, analysis or code, and manuscript drafting. People direct Agentic-Powered-Research and remain responsible for the work and disclosures.

Open [the online searchable directory](https://open-source-research-initiative.github.io/venues/) or the [standalone HTML](index.html), [browse by subfield](DIRECTORY.md), or download [CSV](data/venues.csv) and [JSON](data/venues.json). The standalone HTML works offline; external source links require a network connection.

The default view requires verified free submission and publication and peer review. Conditional or unverified routes are available through the fee filter. Each result shows submission and publication costs, concrete AI disclosure instructions and reported metrics. Venue country and region filters use the owning body or editorial host; publisher location, author eligibility and research focus are separately recorded. Read the source and current venue instructions before submitting.

Acceptance rates and citation metrics retain their reported names, periods, populations and sources. Missing values remain missing. A journal citation metric does not predict an individual manuscript's acceptance or quality. Read the [methodology](docs/methodology.md) for limits and the research process.

## Coverage and maintenance

The [author-cost follow-up](docs/cost-verification.md) rechecked all 74 previously unresolved AI-compatible venues. Four routes now qualify, bringing the verified free peer-reviewed list to 74; 70 remain cost-unverified. The new audit and independent review evidence is preserved alongside the original campaign.

See [coverage](COVERAGE.md), [research notes](RESEARCH_NOTES.md), [assignments](data/agent-assignments.json), and the [build receipt](data/build-receipt.json). Agent evidence review is not independent human scientific review or venue endorsement. Initial healthcare work is nonclinical; new physical laboratory experiments are outside OSRI's initial scope.

Use Python 3 to build and verify the directory:

```bash
python3 scripts/build.py
python3 scripts/check.py
```

The active campaign's five research roles and input requirements are specified in its [contract](research/campaigns/2026-11-16-expansion/CONTRACT.md). The build receipt records input hashes and completion. Edit source research records and rebuild rather than editing generated files. [venues.json](data/venues.json) contains the main eligible list; [candidates.json](data/candidates.json) retains audited candidates, and [excluded-venues.json](data/excluded-venues.json) records exclusions. See [CONTRIBUTING.md](CONTRIBUTING.md) for evidence requirements.

Original guides and catalog compilations use CC BY 4.0; original code uses MIT. [Third-party terms remain separate](LICENSE.md).
