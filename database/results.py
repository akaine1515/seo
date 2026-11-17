"""Versioned analysis snapshots; legacy event snapshots remain readable."""
import copy
import json
from database.connection import database_connection


class AnalysisResultRepository:
    @staticmethod
    def save(run_id: int, result: dict, retain_text: bool = False) -> None:
        snapshot = copy.deepcopy(result)
        if not retain_text:
            for page in snapshot.get('competitor_analysis', []):
                page.pop('raw_text', None)
        with database_connection() as connection:
            connection.execute('INSERT INTO analysis_results (analysis_run_id, format_version, result_json) '
                               'VALUES (?, 1, ?)', (run_id, json.dumps(snapshot, ensure_ascii=False)))

    @staticmethod
    def load(run_id: int):
        with database_connection() as connection:
            row = connection.execute('SELECT format_version, result_json FROM analysis_results '
                                     'WHERE analysis_run_id=?', (run_id,)).fetchone()
            if row:
                if row['format_version'] != 1:
                    raise ValueError('Unsupported analysis snapshot version')
                return json.loads(row['result_json'])
            row = connection.execute("SELECT details_json FROM crawl_events WHERE analysis_run_id=? "
                                     "AND event_type='pipeline_completed' ORDER BY id DESC LIMIT 1", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def compare(previous_run_id: int, current_run_id: int) -> dict:
        before, after = (AnalysisResultRepository.load(i) for i in (previous_run_id, current_run_id))
        if before is None or after is None:
            raise ValueError('Both runs must have saved analysis results')
        if before['meta']['project_id'] != after['meta']['project_id']:
            raise ValueError('Runs must belong to the same project')
        def issues(result):
            return {(i['rule_id'], i['url']) for i in result['audit_summary']['issues']}
        old, new = issues(before), issues(after)
        observed_urls = {p['url'] for p in after.get('crawled_pages', [])}
        removed = old-new
        return {'previous_run_id': previous_run_id, 'current_run_id': current_run_id,
                'added': [dict(rule_id=r, url=u) for r, u in sorted(new-old)],
                'resolved': [dict(rule_id=r, url=u) for r, u in sorted(removed) if u in observed_urls],
                'unobserved': [dict(rule_id=r, url=u) for r, u in sorted(removed) if u not in observed_urls],
                'limitation': 'Changes reflect observed crawl coverage; unresolved URLs may not have been recrawled.'}
