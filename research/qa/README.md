# Verification record

The build and data checks use Python 3's standard library. The campaign build receipt records input hashes, agent assignments, completion and conflicts. Run `python3 scripts/check.py` after rebuilding to verify the current artifacts.

`scripts/browser-check.cjs` uses an existing Playwright installation and Chromium. The optional `OSRI_PLAYWRIGHT_MODULE` and `OSRI_CHROMIUM` environment variables select those installations. The check records HTML and catalog hashes and covers the AI gate, separate costs, default peer review, fee and quality filters, quality status options and reset, index evidence links, venue and publisher geography filters, linked provenance, count labels, subfield filters, disclosures, reported metrics and sorting, empty state, reset, and mobile overflow. Screenshots and `browser-check.json` are generated results and must be refreshed after the catalog or HTML changes.

These checks assess the recorded evidence and rendered behavior. They are not independent human scientific review or a guarantee that venue policies remain unchanged.

The current browser check covers the three browsing modes, comparison and URL state. Set `OSRI_QA_OUTPUT` to a workspace folder outside the checkout for fresh screenshots. Earlier committed screenshots remain historical; `browser-check.json` hashes the current catalog and standalone HTML. The Browser plugin was unavailable, so the existing Playwright runtime was used.
