"""Workspace sites: at most five registered domains; legacy project rows preserved."""
import json
import copy
from urllib.parse import urlparse
from core.domains import site_domain
from database.connection import database_connection
from modules.competitors.discovery import CompetitorDiscovery

DEFAULT_SETTINGS = dict(max_pages=50, max_depth=5, timeout=15, request_interval=0.5,
                        max_response_bytes=5 * 1024 * 1024, excluded_paths=[])


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) - set(DEFAULT_SETTINGS):
        raise ValueError('Unknown crawl settings')
    values = copy.deepcopy({**DEFAULT_SETTINGS, **settings})
    for key in ('max_pages', 'timeout', 'max_response_bytes', 'max_depth'):
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < (0 if key == 'max_depth' else 1):
            raise ValueError(f'Invalid {key}')
    interval = values['request_interval']
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 0 <= interval <= 60:
        raise ValueError('Request interval must be between 0 and 60 seconds')
    paths = values['excluded_paths']
    if not isinstance(paths, list) or any(not isinstance(p, str) or not p.startswith('/') for p in paths):
        raise ValueError('Excluded paths must be a list of absolute path prefixes')
    return values


class SiteRepository:
    @staticmethod
    def register(name: str, url: str) -> int:
        if not isinstance(name, str) or not name.strip() or not isinstance(url, str):
            raise ValueError('Site name and URL are required')
        url = url.strip()
        if '://' not in url:
            url = 'https://' + url
        if not CompetitorDiscovery._is_valid_url(url):
            raise ValueError('Invalid site HTTP URL')
        parsed = urlparse(url)
        domain = site_domain(url)
        hostname = parsed.hostname.lower().rstrip('.')
        port = parsed.port
        netloc = hostname + (f':{port}' if port and (parsed.scheme, port) not in [('https', 443), ('http', 80)] else '')
        url = parsed._replace(netloc=netloc, path=parsed.path or '/', fragment='').geturl()
        with database_connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            sites = connection.execute('SELECT website_url FROM projects').fetchall()
            if any(site_domain(row['website_url']) == domain for row in sites):
                raise ValueError('This site is already registered')
            if len(sites) >= 5:
                raise ValueError('The workspace supports at most five sites, including inactive sites')
            cursor = connection.execute('INSERT INTO projects(name, website_url, domain) VALUES (?, ?, ?)',
                                        (name.strip(), url, domain))
            connection.execute('INSERT INTO site_settings(project_id, settings_json) VALUES (?, ?)',
                               (cursor.lastrowid, json.dumps(DEFAULT_SETTINGS)))
            return cursor.lastrowid

    @staticmethod
    def configure(project_id: int, *, settings=None, active=None, name=None):
        if settings is not None and not isinstance(settings, dict):
            raise ValueError('settings must be a dictionary')
        if active is not None and not isinstance(active, bool):
            raise ValueError('active must be boolean')
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise ValueError('Site name is required')
        with database_connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if not connection.execute('SELECT id FROM projects WHERE id=?', (project_id,)).fetchone():
                raise ValueError('Site does not exist')
            row = connection.execute('SELECT * FROM site_settings WHERE project_id=?', (project_id,)).fetchone()
            current = json.loads(row['settings_json']) if row else DEFAULT_SETTINGS
            values = validate_settings({**current, **(settings or {})})
            enabled = int(active) if active is not None else (row['is_active'] if row else 1)
            connection.execute('INSERT INTO site_settings(project_id, is_active, settings_json) VALUES (?, ?, ?) '
                               'ON CONFLICT(project_id) DO UPDATE SET is_active=excluded.is_active, settings_json=excluded.settings_json',
                               (project_id, enabled, json.dumps(values)))
            if name is not None:
                connection.execute('UPDATE projects SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (name.strip(), project_id))

    @staticmethod
    def list_sites():
        with database_connection() as connection:
            rows = connection.execute('SELECT p.*, s.is_active, s.settings_json FROM projects p '
                                      'LEFT JOIN site_settings s ON s.project_id=p.id ORDER BY p.id').fetchall()
        sites = []
        for row in rows:
            item = dict(row)
            item['is_active'] = bool(item['is_active']) if item['is_active'] is not None else True
            item['settings'] = validate_settings(json.loads(item.pop('settings_json') or '{}'))
            sites.append(item)
        return sites

    @staticmethod
    def status(project_id: int) -> dict:
        with database_connection() as connection:
            run = connection.execute('SELECT r.id, r.status, r.started_at, a.result_json FROM analysis_runs r '
                'LEFT JOIN analysis_results a ON a.analysis_run_id=r.id '
                'WHERE r.project_id=? ORDER BY r.id DESC LIMIT 1', (project_id,)).fetchone()
        if run is None:
            return {'state': 'ready', 'run_id': None}
        state = run['status']
        if state not in ('running', 'pending'):
            state = (json.loads(run['result_json'])['meta'].get('pipeline_status', 'partial')
                     if run['result_json'] else 'partial' if state == 'completed' else state)
        return {'state': state, 'run_id': run['id'], 'started_at': run['started_at']}
