"""Download official SCF microdata and extracts; Python 3 + curl required.
Usage: python get_data.py [--output data/raw] [--refresh]
Parental education starts in 2016; do not extrapolate it to 1989.
"""
import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
from urllib.parse import urljoin

BASE = 'https://www.federalreserve.gov'
YEARS = (2016, 2019, 2022, 2025)

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href', '')
            self.links.append(urljoin(BASE, href))

def download(url, dest, refresh=False):
    if refresh or not dest.exists():
        tmp = dest.with_suffix(dest.suffix + '.part')
        subprocess.run(['curl', '-L', '--fail', '--silent', '--show-error',
                        '--retry', '3', '--max-time', '180', url, '-o', str(tmp)], check=True)
        tmp.replace(dest)
    return {'url': url, 'file': dest.name, 'bytes': dest.stat().st_size,
            'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path(__file__).parent / 'data/raw')
    p.add_argument('--refresh', action='store_true')
    args = p.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    manifest = {'retrieved_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'parental_education_first_year': 2016, 'files': []}
    for year in YEARS:
        page = BASE + ('/econres/scfindex.htm' if year == 2025 else f'/econres/scf_{year}.htm')
        dest = args.output / f'scf_{year}.html'
        manifest['files'].append(download(page, dest, args.refresh))
        parser = Links(); parser.feed(dest.read_text())
        yy = str(year)
        # Resolve actual links from the official year page, never a third-party mirror.
        names = [f'scf{yy}s.zip', f'scfp{year}excel.zip', f'scf{yy}rw1s.zip', f'codebk{year}.txt']
        for name in names:
            matches = [u for u in parser.links if u.rsplit('/', 1)[-1].lower() == name.lower()]
            if not matches and name.startswith('codebk'):
                matches = [u for u in parser.links if 'codebk' in u.lower() and u.endswith('.txt')]
            if not matches:
                raise RuntimeError(f'Official download link not found: {year} {name}')
            url = matches[0]
            manifest['files'].append(download(url, args.output / url.rsplit('/',1)[-1], args.refresh))
        print(f'Downloaded {year}', flush=True)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')

if __name__ == '__main__':
    main()
