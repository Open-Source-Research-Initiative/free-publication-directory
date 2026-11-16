# Contribute a venue or correction

Start with an official journal, society, university, publisher, or repository page. State the subfield and kind of research that fits. A directory entry is a factual record, not a promise of acceptance or an endorsement of every article the venue publishes.

Record the submission and standard publication costs separately. Check excess-page charges, compulsory membership, conference registration, article types, open-access options, and author eligibility. A waiver or institutional agreement is conditional. Mark unclear costs as `needs_verification` and retain the source and reason.

For metrics, use an official source and preserve the number's name, year or reporting period, and population. Do not infer an acceptance rate from rejection statistics, multiply conditional rates, or turn citation metrics into acceptance odds. Explain a proposed difficulty band using the venue's editorial criteria or reported selectivity, with source links. Unknown is an acceptable result.

Add a candidate in the relevant `research/discovery/<subfield>.json` or `research/diamond/<subfield>.json` file using [the record contract](research/CONTRACT.md). Retain its stable ID when correcting it. Subsequent fee, ranking, and review patches refer to that ID. A correction made after those reviews must be checked against their conclusions; rebuild and rerun the checks.

Have a different person or agent inspect the fee evidence and any changed ranking before adding the venue to a recommended list. State who performed the review and what remains unchecked. Agent review does not replace a human lead's decision to submit.

Run `python3 scripts/build.py` and `python3 scripts/check.py`. Inspect the generated field page and filtered HTML directory. Keep the data, generated files, and evidence receipt together in the change. Maintainers authorize publication separately.
