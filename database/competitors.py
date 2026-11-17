"""Persistent independent competitor choices per site and normalized keyword."""
import json
from database.connection import database_connection
from modules.keywords.analyzer import KeywordAnalyzer


def validate_choices(mapping, candidates=None):
    if not isinstance(mapping, dict):
        raise ValueError('انتخاب رقبا باید به تفکیک کلمه باشد.')
    cleaned = {}
    for term, domains in mapping.items():
        if not isinstance(term, str) or not term.strip() or not isinstance(domains, list):
            raise ValueError('کلمه و فهرست دامنه معتبر لازم است.')
        term = KeywordAnalyzer.normalize_keyword(term)
        if term in cleaned or any(not isinstance(d, str) or not d for d in domains):
            raise ValueError('انتخاب تکراری یا نامعتبر است.')
        if len(domains) > 5 or len(set(domains)) != len(domains):
            raise ValueError('برای هر کلمه حداکثر پنج رقیب متفاوت انتخاب کنید.')
        if candidates is not None and any(d not in {r['domain'] for r in candidates.get(term, [])} for d in domains):
            raise ValueError('رقیب باید در نتایج SERP همین کلمه حضور داشته باشد.')
        cleaned[term] = list(domains)
    return cleaned


class CompetitorChoiceRepository:
    @staticmethod
    def load(project_id):
        with database_connection() as conn:
            rows = conn.execute('SELECT keyword, domains_json FROM keyword_competitor_choices WHERE project_id=?', (project_id,)).fetchall()
        return {row['keyword']: json.loads(row['domains_json']) for row in rows}

    @staticmethod
    def save(project_id, mapping, candidates):
        mapping = validate_choices(mapping, candidates)
        with database_connection() as conn:
            for term, domains in mapping.items():
                conn.execute('INSERT INTO keyword_competitor_choices(project_id, keyword, domains_json) VALUES (?, ?, ?) '
                             'ON CONFLICT(project_id, keyword) DO UPDATE SET domains_json=excluded.domains_json, updated_at=CURRENT_TIMESTAMP',
                             (project_id, term, json.dumps(domains)))
