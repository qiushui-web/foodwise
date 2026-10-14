"""Read public source documentation and metadata; no private upload or CSV download."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import base64
import hashlib
import json
from urllib.request import Request, urlopen
from urllib.parse import quote
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[2]


def console_json(value):
    return json.dumps(value, ensure_ascii=True, indent=2)


def fetch(url):
    request = Request(url, headers={'User-Agent': 'Foodwise-provenance-review/1.0',
                                    'Accept': 'application/vnd.github+json' if 'api.github.com' in url else 'text/html'})
    with urlopen(request, timeout=20) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('Documentation exceeds bounded read limit')
        return response.status, response.url, body


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip-1)

    def handle_data(self, text):
        if not self.skip and text.strip():
            self.texts.append(text.strip())


def main():
    run = ROOT/'modeling/data/03_output'/('provenance_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(parents=True, exist_ok=False)
    records = []
    def record(url, kind):
        try:
            status, resolved, body = fetch(url)
            item = dict(url=url, resolved_url=resolved, kind=kind, http_status=status,
                        body_sha256=hashlib.sha256(body).hexdigest(), success=True)
            records.append(item)
            return body, item
        except Exception as error:
            records.append(dict(url=url, kind=kind, success=False, error=str(error)))
            return None, None
    official = 'https://www.green-ai-hub.de/pilotprojekte/pilotprojekt-brammibals-donuts-foodtracks'
    body, official_item = record(official, 'official_pilot_page')
    if body is not None:
        parser = TextParser()
        parser.feed(body.decode('utf-8', errors='replace'))
        texts = '\n'.join(parser.texts)
        relevant = [line for line in parser.texts if any(term in line.lower() for term in
                    ('bramm', 'foodtrack', 'prognos', 'verkauf', 'daten', 'spend', 'forecast', 'waste'))]
        official_item['relevant_excerpts'] = relevant[:30]
        official_item['matches_expected_project_names'] = 'bramm' in texts.lower() and 'foodtrack' in texts.lower()
        (run/'official_page_text.txt').write_text(texts, encoding='utf-8')
    query = 'https://api.github.com/search/repositories?q='+quote('Reduce-Foodwaste-Dataset')+'&per_page=5'
    body, search_item = record(query, 'repository_discovery')
    repositories = []
    if body is not None:
        search = json.loads(body)
        repositories = [item for item in search.get('items', []) if item['name'].lower() == 'reduce-foodwaste-dataset']
        search_item['exact_name_matches'] = [item['full_name'] for item in repositories]
    if len(repositories) == 1:
        repo = repositories[0]
        repo_info = dict(full_name=repo['full_name'], html_url=repo['html_url'], owner=repo['owner']['login'],
                         description=repo.get('description'), default_branch=repo['default_branch'],
                         association='Name/discovery match; official publisher ownership requires separate evidence')
        (run/'repository.json').write_text(json.dumps(repo_info, ensure_ascii=False, indent=2), encoding='utf-8')
        for filename in ('README.md', 'LICENSE', 'train.csv'):
            url = f'https://api.github.com/repos/{repo["full_name"]}/contents/{filename}?ref={quote(repo["default_branch"])}'
            body, item = record(url, 'upstream_file_metadata')
            if body is None:
                continue
            meta = json.loads(body)
            local = ROOT/'modeling/data/01_raw/reduce_foodwaste'/filename
            local_body = local.read_bytes()
            local_blob_sha = hashlib.sha1(b'blob '+str(len(local_body)).encode()+b'\0'+local_body).hexdigest()
            item.update(filename=filename, upstream_git_blob_sha=meta.get('sha'), local_git_blob_sha=local_blob_sha,
                        matches_local_bytes=meta.get('sha') == local_blob_sha, upstream_size=meta.get('size'))
            if filename != 'train.csv' and meta.get('encoding') == 'base64':
                content = base64.b64decode(meta['content'])
                (run/('upstream_'+filename)).write_bytes(content)
                item['document_sha256'] = hashlib.sha256(content).hexdigest()
    report = dict(reviewed_at=datetime.now(timezone.utc).isoformat(), records=records,
        local_scope='Aggregate public documentation and CSV metadata only; no personal-data access',
        interpretation='File matching verifies copy consistency, not original sampling authenticity or absence of upstream scaling leakage',
        pending=['Exact scaling formula and fitting time period', 'Explicit data-specific rights scope',
                 'Local Hebei raw labels and authorization'])
    (run/'review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (run/'22_upstream_provenance_review.py').write_bytes(Path(__file__).read_bytes())
    print(console_json(dict(run=str(run), **report)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay-review', type=Path, help='Display an existing saved review without refetching')
    args = parser.parse_args()
    if args.replay_review:
        print(console_json(json.loads(args.replay_review.read_text(encoding='utf-8'))))
    else:
        main()
