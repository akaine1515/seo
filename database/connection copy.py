
from pathlib import Path
import sqlite3
from contextlib import contextmanager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "seo_intelligence.db"

CURRENT_SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    website_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(website_url)
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    started_at TEXT,
    finished_at TEXT,
    max_pages INTEGER NOT NULL DEFAULT 50,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT,
    title TEXT,
    meta_description TEXT,
    h1 TEXT,
    status_code INTEGER,
    content_type TEXT,
    word_count INTEGER DEFAULT 0,
    depth INTEGER DEFAULT 0,
    is_indexable INTEGER DEFAULT 1,
    robots_directive TEXT,
    canonical_status TEXT,
    content_hash TEXT,
    crawled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id)
        ON DELETE CASCADE,
    UNIQUE(analysis_run_id, url)
);

CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    normalized_keyword TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, normalized_keyword)
);

CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    domain TEXT NOT NULL,
    website_url TEXT,
    discovered_by_keyword TEXT,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, domain)
);

CREATE TABLE IF NOT EXISTS competitor_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    analysis_run_id INTEGER NOT NULL,
    search_position INTEGER,
    result_url TEXT,
    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(competitor_id) REFERENCES competitors(id) ON DELETE CASCADE,
    FOREIGN KEY(keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
    FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE,
    UNIQUE(competitor_id, keyword_id, analysis_run_id)
);

CREATE TABLE IF NOT EXISTS keyword_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword_id INTEGER NOT NULL,
    analysis_run_id INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    unit TEXT,
    source_name TEXT NOT NULL,
    source_url TEXT,
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
    FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS page_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    frequency INTEGER DEFAULT 0,
    density REAL DEFAULT 0,
    tf_idf_score REAL,
    relevance_score REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE,
    FOREIGN KEY(keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
    UNIQUE(page_id, keyword_id)
);

CREATE TABLE IF NOT EXISTS technical_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL,
    page_id INTEGER,
    issue_code TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL
        CHECK(severity IN ('critical', 'high', 'medium', 'low', 'info')),
    title TEXT NOT NULL,
    description TEXT,
    recommendation TEXT,
    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS content_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    competitor_id INTEGER,
    target_has_topic INTEGER NOT NULL DEFAULT 0,
    competitor_has_topic INTEGER NOT NULL DEFAULT 1,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
    FOREIGN KEY(competitor_id) REFERENCES competitors(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    analysis_run_id INTEGER,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    reference_url TEXT,
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL,
    FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runs_project
ON analysis_runs(project_id);

CREATE INDEX IF NOT EXISTS idx_pages_run
ON pages(analysis_run_id);

CREATE INDEX IF NOT EXISTS idx_keywords_project
ON keywords(project_id);

CREATE INDEX IF NOT EXISTS idx_competitors_project
ON competitors(project_id);

CREATE INDEX IF NOT EXISTS idx_metrics_keyword
ON keyword_metrics(keyword_id);

CREATE INDEX IF NOT EXISTS idx_issues_run
ON technical_issues(analysis_run_id);

CREATE INDEX IF NOT EXISTS idx_gaps_run
ON content_gaps(analysis_run_id);
"""

PAGE_COLUMNS_V2 = {
    "title_length": "INTEGER DEFAULT 0",
    "meta_description_length": "INTEGER DEFAULT 0",
    "h1_count": "INTEGER DEFAULT 0",
    "h2_count": "INTEGER DEFAULT 0",
    "h3_count": "INTEGER DEFAULT 0",
    "headings_json": "TEXT",
    "image_count": "INTEGER DEFAULT 0",
    "images_without_alt": "INTEGER DEFAULT 0",
    "internal_links_count": "INTEGER DEFAULT 0",
    "external_links_count": "INTEGER DEFAULT 0",
    "x_robots_tag": "TEXT",
    "is_nofollow": "INTEGER DEFAULT 0",
}


def get_connection():
    """Create and return a configured SQLite connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


@contextmanager
def database_connection():
    """Provide a connection with automatic commit/rollback."""
    connection = get_connection()

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def migrate_database(connection):
    """Apply database migrations without deleting existing records."""

    connection.execute("""
        INSERT OR IGNORE INTO schema_versions (version)
        VALUES (1)
    """)

    applied_versions = {
        row["version"]
        for row in connection.execute(
            "SELECT version FROM schema_versions"
        ).fetchall()
    }

    if 2 not in applied_versions:
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(pages)"
            ).fetchall()
        }

        for column_name, column_definition in PAGE_COLUMNS_V2.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE pages ADD COLUMN "
                    f"{column_name} {column_definition}"
                )

        connection.execute("""
            INSERT INTO schema_versions (version)
            VALUES (2)
        """)

    connection.commit()


def initialize_database():
    """Create tables and apply migrations."""

    with database_connection() as connection:
        connection.executescript(SCHEMA)
        migrate_database(connection)

    print(f"Database initialized: {DB_PATH}")


if __name__ == "__main__":
    initialize_database()
