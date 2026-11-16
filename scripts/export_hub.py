#!/usr/bin/env python3
"""Export a checked snapshot to an explicitly selected OSRI hub checkout."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from build import ROOT
from check import check


def export(hub):
    check()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip(), 'Commit the reviewed directory before exporting a source-pinned snapshot.'
    hub = hub.resolve()
    assert (hub / 'site/build.py').is_file() and (hub / 'publications/README.md').is_file(), 'Choose an OSRI hub checkout.'
    target = hub / 'publications/venues'
    target.mkdir(exist_ok=True)
    text = (ROOT / 'DIRECTORY.md').read_text().replace('docs/subfields/', 'subfields/').replace('docs/methodology.md', 'methodology.md')
    text += '\nThis is a generated snapshot of the OSRI free-publication directory. The [snapshot manifest](snapshot.json) and [evidence receipt](build-receipt.json) preserve its source hashes. [Download the venue CSV](venues.csv), [inspect JSON](venues.json), or read the [agent findings and excluded leads](RESEARCH_NOTES.md).\n'
    (target / 'README.md').write_text(text)
    shutil.copy2(ROOT / 'docs/methodology.md', target / 'methodology.md')
    shutil.copy2(ROOT / 'index.html', target / 'browser.html')
    shutil.copytree(ROOT / 'docs/subfields', target / 'subfields', dirs_exist_ok=True)
    for source in ['data/venues.csv', 'data/venues.json', 'data/build-receipt.json', 'data/validation.json']:
        shutil.copy2(ROOT / source, target / Path(source).name)
    shutil.copy2(ROOT / 'RESEARCH_NOTES.md', target / 'RESEARCH_NOTES.md')
    (target / 'research').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'research/CONTRACT.md', target / 'research/CONTRACT.md')
    for entry in json.loads((ROOT / 'data/build-receipt.json').read_text())['inputs']:
        source = ROOT / entry['path']
        destination = target / entry['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {'source_repository': 'free-publication-directory', 'source_commit': commit, 'checked_on': '2026-11-16', 'files': []}
    for path in sorted(target.rglob('*')):
        if path.is_file() and path.name != 'snapshot.json':
            manifest['files'].append({'path': str(path.relative_to(target)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (target / 'snapshot.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'hub': str(hub), 'snapshot_commit': commit, 'files': len(manifest['files'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hub', type=Path)
    export(parser.parse_args().hub)
