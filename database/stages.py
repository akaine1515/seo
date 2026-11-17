"""Append-only execution history for analysis stages derived from saved crawls."""
import copy
import json
from datetime import datetime, timezone
from database.connection import database_connection


class StageResultRepository:
    @staticmethod
    def start(source_run_id, algorithm_version):
        with database_connection() as conn:
            cursor = conn.execute("INSERT INTO analysis_stage_results "
                "(source_analysis_run_id, stage_name, status, algorithm_version, started_at) "
                "VALUES (?, 'competitors', 'running', ?, ?)",
                (source_run_id, algorithm_version, datetime.now(timezone.utc).isoformat()))
            return cursor.lastrowid

    @staticmethod
    def finish(stage_id, status, result=None, retain_text=False, error_type=None):
        if status not in {'completed', 'partial', 'failed', 'cancelled'}:
            raise ValueError('Invalid terminal stage status')
        snapshot = copy.deepcopy(result)
        if snapshot is not None and not retain_text:
            for page in snapshot.get('competitor_analysis', []):
                page.pop('raw_text', None)
        with database_connection() as conn:
            cursor = conn.execute('UPDATE analysis_stage_results SET status=?, finished_at=?, '
                "result_json=?, error_type=? WHERE id=? AND status='running'",
                (status, datetime.now(timezone.utc).isoformat(),
                 json.dumps(snapshot, ensure_ascii=False) if snapshot is not None else None,
                 error_type, stage_id))
            if cursor.rowcount != 1:
                raise ValueError('Stage is missing or already finalized')

    @staticmethod
    def load(stage_id):
        with database_connection() as conn:
            row = conn.execute('SELECT format_version, result_json FROM analysis_stage_results WHERE id=?', (stage_id,)).fetchone()
        if row is None or row['result_json'] is None:
            return None
        if row['format_version'] != 1:
            raise ValueError('Unsupported stage snapshot version')
        return json.loads(row['result_json'])

    @staticmethod
    def list_for_project(project_id):
        with database_connection() as conn:
            rows = conn.execute('SELECT s.id, s.source_analysis_run_id, s.stage_name, s.status, '
                's.started_at, s.finished_at, s.algorithm_version, s.error_type '
                'FROM analysis_stage_results s JOIN analysis_runs r ON r.id=s.source_analysis_run_id '
                'WHERE r.project_id=? ORDER BY s.id DESC', (project_id,)).fetchall()
        return [dict(row) for row in rows]
