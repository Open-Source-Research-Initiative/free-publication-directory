# Help improve the venue directory

A browser and a short note are enough. You can check a source, suggest a correction, or tell us what happened when you tried to find venues for your research. No coding, fork, data-file editing, academic credential or paid tool is required.

## Choose one way to help

- [Choose a starter task](https://github.com/Open-Source-Research-Initiative/free-publication-directory/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22): each has a starting source, a suggested timebox and a clear result to return. Comment to volunteer and wait for a maintainer to confirm the claim. Small corrections can be submitted directly.
- [Report a correction or source](https://github.com/Open-Source-Research-Initiative/free-publication-directory/issues/new?template=venue-evidence.yml): tell us what you found and link the official page. A lead or unresolved question is welcome.
- [Share a directory-use report](https://github.com/Open-Source-Research-Initiative/free-publication-directory/issues/new?template=directory-use.yml): try one public research topic, then share a shortlist and what helped or got in the way. A reason no venue fits is useful too.

Without a GitHub account, [email Cole](mailto:cole.lyons@pennmedicine.upenn.edu?subject=OSRI%20venue%20directory%20contribution) with the same note. A maintainer can prepare a public record with your permission. Public credit is optional. A public topic description is enough to participate; no manuscript upload is needed.

## What to put in a source note

1. The venue and the observation or proposed correction.
2. The official URL, relevant section, and date you checked it.
3. Conditions or uncertainty that change the meaning. If a page was blocked or unreadable, say so.
4. Material AI/agent assistance, if used, and your preferred public credit name/handle or a request for no public credit.

A short paraphrase is enough; do not copy entire publisher pages. For an interface problem, describe the steps and what you expected. You do not need an official policy source for a usability report.

## What happens next

Cole / @ajhcs is the human maintainer. Maintainers review the note, ask about gaps, and prepare any evidence or data changes. Agent checks are identified separately from human review. A submitted note does not automatically change a venue's status.

Useful checks can confirm an existing record. Accepted contributions are recorded once per agreed task under [OSRI's contribution rules](https://github.com/Open-Source-Research-Initiative/osri/blob/main/community/README.md); revisions do not create extra tasks. Credit does not promise manuscript authorship. We ask separately before quoting your experience publicly. During the launch, claim one task at a time; maintainers start with at most three active claims across the starter issues.

## Keep the evidence precise

- Record **submission cost and publication cost separately**. Check mandatory page charges, membership, registration, article types and author eligibility. Optional open access and reader subscriptions are separate. Waivers and institutional agreements are conditional; silence about charges does not prove zero cost.
- Link the applicable **AI policy and disclosure instructions**. Preserve what it says about research, analysis/code and drafting, including restrictions and where disclosure belongs. Editing-only permission or policy silence does not qualify for the main directory.
- Separate venue/owning-body location, publisher location, author eligibility and research focus. One does not establish the others.
- For a metric, keep its reported name, value, period, population and official source. Do not invent difficulty bands or turn citation metrics into acceptance odds.
- Distinguish indexing confirmation, publisher claims and unresolved access. Documented editorial policies and a traceable article do not certify individual papers. Missing evidence does not establish misconduct.

## For maintainers and people submitting patches

Read the [active expansion contract](research/campaigns/2026-11-16-expansion/CONTRACT.md), [cost follow-up](research/campaigns/2026-11-16-cost-followup/CONTRACT.md), [quality campaign](research/campaigns/2026-11-16-quality/CONTRACT.md), and [current display policy](docs/display-policy.md). The original discovery contract is historical; it is not the current newcomer entry point.

Keep stable venue IDs and original campaign evidence intact. Agree a separately dated follow-up for new accepted evidence rather than silently rewriting historical decisions. Include the source, interpretation, actual checks and remaining review in the proposed change. Have another person or agent inspect changed cost or metric evidence; identify the reviewer's role accurately.

For changes that affect directory outputs, run `python3 scripts/build.py` and `python3 scripts/check.py`, plus the relevant fee or quality follow-up checks. Inspect the generated field page and browser, and keep generated outputs and their evidence receipt together. Do not edit generated data or HTML directly. A human maintainer authorizes acceptance and publication.
