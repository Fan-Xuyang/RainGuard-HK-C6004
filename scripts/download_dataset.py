"""Download the frozen official dataset release, verify its digest, and unpack safely."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request
import zipfile


def main():
    repo=Path(__file__).resolve().parents[1]
    metadata=json.loads((repo/'datasets/release.json').read_text(encoding='utf-8'))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,help='Use an already-downloaded release ZIP')
    args=parser.parse_args()
    target=repo/'datasets'
    existing=target/'RainGuard_HK_Dataset'
    if existing.exists():
        raise SystemExit('Dataset directory already exists. Keep its changes; use collector --offline or --live-only instead.')
    with tempfile.TemporaryDirectory(prefix='rainguard-dataset-') as tmp:
        archive=args.archive or Path(tmp)/metadata['asset_name']
        if not args.archive:
            print('Downloading official project release dataset...',flush=True)
            request=urllib.request.Request(metadata['download_url'],headers={'User-Agent':'RainGuard-HK-Dataset-Download'})
            with urllib.request.urlopen(request,timeout=120) as response,archive.open('wb') as output:
                while block:=response.read(1024*1024):output.write(block)
        digest=hashlib.sha256()
        with archive.open('rb') as source:
            while block:=source.read(1024*1024):digest.update(block)
        if digest.hexdigest()!=metadata['sha256']:raise SystemExit('Checksum mismatch: nothing extracted.')
        with zipfile.ZipFile(archive) as z:
            root=target.resolve()
            for info in z.infolist():
                resolved=(target/info.filename).resolve()
                if not resolved.is_relative_to(root) or not info.filename.startswith('RainGuard_HK_Dataset/'):
                    raise SystemExit('Unexpected archive path: nothing extracted.')
                if ((info.external_attr>>16)&0o170000)==0o120000:
                    raise SystemExit('Archive symlink is not allowed.')
            if z.testzip() is not None:raise SystemExit('Damaged archive: nothing extracted.')
            z.extractall(target)
    print('SHA-256 verified; dataset ready at',existing)


if __name__=='__main__':main()
