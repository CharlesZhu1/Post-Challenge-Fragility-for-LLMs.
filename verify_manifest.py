#!/usr/bin/env python3
"""Check this release's shipped file SHA-256s before running the analyses."""
from pathlib import Path
import hashlib, csv, sys
root = Path(__file__).resolve().parent
manifest = root / 'FILE_SHA256_MANIFEST.csv'
with manifest.open(encoding='utf-8-sig', newline='') as f:
    entries = list(csv.DictReader(f))
failed = []
for entry in entries:
    relative = entry['relative_path']
    if relative.startswith('/') or '..' in Path(relative).parts:
        failed.append(relative + ': unsafe manifest path')
        continue
    path = root / relative
    if not path.is_file():
        failed.append(relative + ': missing')
        continue
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != entry['sha256']:
        failed.append(relative + ': SHA-256 mismatch')
if failed:
    print('FAIL: integrity check')
    print('\n'.join(failed))
    sys.exit(1)
print(f'PASS: {len(entries)} release files match the SHA-256 manifest')
