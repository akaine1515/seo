"""SERP boundary: import results exported by an authorized provider.

No direct Google scraping or fabricated fallback. A live provider can implement
source and search(keywords) with the same return contract.
"""
import copy
from datetime import datetime
from modules.competitors.discovery import CompetitorDiscovery
import json
from pathlib import Path
from modules.keywords.analyzer import KeywordAnalyzer


class FileSERPProvider:
    """JSON: {source, retrieved_at, results: [{keyword, organic_results}]}.

    organic_results items contain url and position. Original source metadata
    is retained; this class performs no network requests.
    """

    def __init__(self, path: str):
        with Path(path).open('rb') as stream:
            raw = stream.read(10 * 1024 * 1024 + 1)
        if len(raw) > 10 * 1024 * 1024:
            raise ValueError('SERP file exceeds 10 MiB')
        self.payload = json.loads(raw.decode('utf-8'))
        if not isinstance(self.payload, dict):
            raise ValueError('SERP file must contain an object')
        for field in ('source', 'retrieved_at'):
            if not isinstance(self.payload.get(field), str) or not self.payload[field].strip():
                raise ValueError(f'SERP file requires {field}')
        if not isinstance(self.payload.get('results'), list):
            raise ValueError('SERP results must be a list')
        try:
            stamp = datetime.fromisoformat(self.payload['retrieved_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('Timezone required')
        except ValueError as error:
            raise ValueError('retrieved_at must be an ISO timestamp with timezone') from error
        if len(self.payload['results']) > 10000:
            raise ValueError('Too many SERP keyword entries')
        for entry in self.payload['results']:
            if not isinstance(entry, dict) or not isinstance(entry.get('keyword'), str) or not entry['keyword'].strip():
                raise ValueError('Each SERP entry requires a keyword')
            rows = entry.get('organic_results')
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError('organic_results must be a list of at most 100 entries')
            for row in rows:
                if (not isinstance(row, dict) or not CompetitorDiscovery._is_valid_url(row.get('url'))
                        or isinstance(row.get('position'), bool)
                        or not isinstance(row.get('position'), int) or row['position'] < 1):
                    raise ValueError('Invalid SERP URL or position')
        self.source = self.payload['source']
        self.retrieved_at = self.payload['retrieved_at']

    def search(self, keywords: list) -> list:
        terms = {KeywordAnalyzer.normalize_keyword(term) for term in keywords}
        return copy.deepcopy([item for item in self.payload['results']
                              if isinstance(item, dict) and
                              KeywordAnalyzer.normalize_keyword(item.get('keyword')) in terms])
