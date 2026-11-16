# Verification record

The directory build and data checks use only Python 3's standard library. `scripts/check.py` verifies all sixty role files, five distinct agent assignments per cluster, source hashes, the merged data, free-route gates, generated export identity, and local Markdown links. It also checks the browser report against the current HTML and catalog hashes when that report is present.

`scripts/browser-check.cjs` uses an existing Playwright installation and Chromium. The optional `OSRI_PLAYWRIGHT_MODULE` and `OSRI_CHROMIUM` environment variables select those installations. Use a Node version supported by the chosen Playwright version, and keep temporary browser profiles on the approved workspace filesystem.

The rendered checks cover default free/peer-review/availability filters, each of the twelve clusters, evidence disclosure, ranking guards, empty results, reset, closed-submission labels, desktop rendering and mobile overflow. Screenshots and `browser-check.json` record the final checked view and source hashes.

During initial qualification, system Node 18 could not run the installed Playwright. The existing reviewed Node 24 runtime and browser dependency sysroot resolved the runtime requirements. A reset button whose ID shadowed the form's native `reset()` method was renamed; the complete interaction check then passed. No system package baseline was changed.

The primary agent independently checked official System Safety author fees and peer-review types, JOSS submission scope, Review of Economic Analysis submission guidance, Sage's charge list and metric definitions, Springer Nature's model-cost caveats, the Diamond Discovery Hub verification method, and DORA's indicator guidance. The separate subfield reviewers report their own source coverage and access failures in the retained role files. These checks do not constitute independent human scientific review or guarantee that a policy will remain unchanged.
