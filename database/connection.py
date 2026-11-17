
from pathlib import Path
import sqlite3
import time
from contextlib import contextmanager


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "seo_intelligence.db"

CURRENT_SCHEMA_VERSION = 10

DATABASE_TIMEOUT = 15
BUSY_TIMEOUT_MS = 15000

MIGRATION_MAX_RETRIES = 5
MIGRATION_RETRY_DELAY = 2


# =========================================================
# BASE DATABASE SCHEMA
# =========================================================

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


# =========================================================
# MIGRATION DEFINITIONS
# =========================================================

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

PAGE_COLUMNS_V3 = {
    "parent_url": "TEXT",
    "final_url": "TEXT",
    "redirect_chain_json": "TEXT",
    "crawl_status": "TEXT NOT NULL DEFAULT 'success'",
    "crawl_error": "TEXT",
    "duplicate_of_url": "TEXT",
    "duplicate_type": "TEXT",
    "unique_internal_links_count": "INTEGER DEFAULT 0",
    "unique_external_links_count": "INTEGER DEFAULT 0",
    "nofollow_links_count": "INTEGER DEFAULT 0",
}


# =========================================================
# CONNECTION MANAGEMENT
# =========================================================

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(DB_PATH),
        timeout=DATABASE_TIMEOUT,
        isolation_level="DEFERRED"
    )

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}"
    )

    return connection


@contextmanager
def database_connection():
    connection = get_connection()

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# MIGRATION HELPERS
# =========================================================

def get_table_columns(connection, table_name):
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {row["name"] for row in rows}


def add_missing_columns(connection, table_name, columns):
    existing_columns = get_table_columns(
        connection,
        table_name
    )

    for column_name, column_definition in columns.items():
        if column_name in existing_columns:
            continue

        connection.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_definition}"
        )

        print(
            f"[MIGRATION] Added column: "
            f"{table_name}.{column_name}"
        )


def register_schema_version(connection, version):
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_versions (version)
        VALUES (?)
        """,
        (version,)
    )


# =========================================================
# MIGRATION: VERSION 1, 2 AND 3
# =========================================================

def migrate_database(connection):
    register_schema_version(connection, 1)

    add_missing_columns(
        connection,
        "pages",
        PAGE_COLUMNS_V2
    )

    register_schema_version(connection, 2)

    add_missing_columns(
        connection,
        "pages",
        PAGE_COLUMNS_V3
    )

    register_schema_version(connection, 3)

    print("[MIGRATION] Schema versions 1, 2 and 3 verified.")


# =========================================================
# MIGRATION: VERSION 4
# =========================================================

def migrate_v4(connection):
    """
    Create all version 4 objects using the current connection.
    """

    connection.execute("""
        CREATE TABLE IF NOT EXISTS crawl_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_run_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            normalized_url TEXT NOT NULL,
            depth INTEGER NOT NULL DEFAULT 0,
            parent_url TEXT,
            discovered_from TEXT,
            priority INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK(status IN (
                    'queued', 'processing', 'completed',
                    'failed', 'blocked', 'skipped'
                )),
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            processed_at TEXT,
            FOREIGN KEY (analysis_run_id)
                REFERENCES analysis_runs(id) ON DELETE CASCADE,
            UNIQUE (analysis_run_id, normalized_url)
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawl_queue_run_status
        ON crawl_queue (analysis_run_id, status)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawl_queue_priority
        ON crawl_queue (
            analysis_run_id, status, priority DESC, id ASC
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawl_queue_depth
        ON crawl_queue (analysis_run_id, depth)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS page_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_run_id INTEGER NOT NULL,
            source_page_id INTEGER NOT NULL,
            target_page_id INTEGER,
            source_url TEXT NOT NULL,
            target_url TEXT NOT NULL,
            anchor_text TEXT,
            rel TEXT,
            is_internal INTEGER NOT NULL DEFAULT 1,
            link_type TEXT NOT NULL DEFAULT 'html',
            link_position INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_run_id)
                REFERENCES analysis_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (source_page_id)
                REFERENCES pages(id) ON DELETE CASCADE,
            FOREIGN KEY (target_page_id)
                REFERENCES pages(id) ON DELETE SET NULL,
            UNIQUE (source_page_id, link_position)
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_page_links_source
        ON page_links (source_page_id)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_page_links_target
        ON page_links (target_url)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_page_links_target_page
        ON page_links (target_page_id)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_page_links_run_internal
        ON page_links (analysis_run_id, is_internal)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS crawl_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_run_id INTEGER NOT NULL,
            url TEXT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            message TEXT,
            details_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_run_id)
                REFERENCES analysis_runs(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawl_events_run
        ON crawl_events (analysis_run_id)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawl_events_type
        ON crawl_events (analysis_run_id, event_type)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawl_events_severity
        ON crawl_events (analysis_run_id, severity)
    """)

    connection.execute("""
        UPDATE crawl_queue
        SET
            status = 'queued',
            updated_at = CURRENT_TIMESTAMP
        WHERE status = 'processing'
    """)

    register_schema_version(connection, 4)


# =========================================================
# MIGRATION: VERSION 5
# =========================================================

def migrate_v5(connection):
    """
    Safely rebuild analysis_runs to support additional lifecycle
    statuses and execution metadata.

    Existing analysis run records and IDs are preserved.
    Foreign key enforcement is temporarily disabled by
    _initialize_once while this migration is running.
    """

    table_info = connection.execute(
        "PRAGMA table_info(analysis_runs)"
    ).fetchall()

    existing_columns = {
        row["name"]
        for row in table_info
    }

    table_sql_row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'analysis_runs'
        """
    ).fetchone()

    table_sql = (
        table_sql_row["sql"].lower()
        if table_sql_row and table_sql_row["sql"]
        else ""
    )

    required_columns = {
        "updated_at",
        "last_heartbeat_at",
        "completion_reason",
        "summary_json"
    }

    needs_rebuild = (
        not required_columns.issubset(existing_columns)
        or "'cancelled'" not in table_sql
        or "'interrupted'" not in table_sql
    )

    if needs_rebuild:

        print(
            "[MIGRATION] Rebuilding analysis_runs "
            "for schema version 5..."
        )

        connection.execute(
            "DROP TABLE IF EXISTS analysis_runs_new"
        )

        connection.execute("""
            CREATE TABLE analysis_runs_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN (
                        'pending',
                        'running',
                        'completed',
                        'failed',
                        'cancelled',
                        'interrupted'
                    )),
                started_at TEXT,
                finished_at TEXT,
                max_pages INTEGER NOT NULL DEFAULT 50,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_heartbeat_at TEXT,
                completion_reason TEXT,
                summary_json TEXT,
                FOREIGN KEY(project_id)
                    REFERENCES projects(id) ON DELETE CASCADE
            )
        """)

        new_columns = [
            "id",
            "project_id",
            "status",
            "started_at",
            "finished_at",
            "max_pages",
            "error_message",
            "created_at",
            "updated_at",
            "last_heartbeat_at",
            "completion_reason",
            "summary_json"
        ]

        columns_to_copy = [
            column
            for column in new_columns
            if column in existing_columns
        ]

        if columns_to_copy:
            column_list = ", ".join(columns_to_copy)

            connection.execute(
                f"""
                INSERT INTO analysis_runs_new ({column_list})
                SELECT {column_list}
                FROM analysis_runs
                """
            )

        connection.execute(
            "DROP TABLE analysis_runs"
        )

        connection.execute(
            "ALTER TABLE analysis_runs_new "
            "RENAME TO analysis_runs"
        )

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_project
            ON analysis_runs(project_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_status
            ON analysis_runs(status)
        """)

        print(
            "[MIGRATION] analysis_runs rebuilt successfully."
        )

    else:
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_status
            ON analysis_runs(status)
        """)

    register_schema_version(connection, 5)

    print("[MIGRATION] Schema version 5 verified.")


# =========================================================
# MIGRATION: VERSION 6
# =========================================================

def migrate_v6(connection):
    """
    Store extracted page content and heading lists separately.

    Each page belongs to a specific analysis run. Therefore,
    page_id provides run-specific content history.
    """

    connection.execute("""
        CREATE TABLE IF NOT EXISTS page_contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            page_id INTEGER NOT NULL UNIQUE,

            text_content TEXT NOT NULL DEFAULT '',

            h1_list_json TEXT,
            h2_list_json TEXT,
            h3_list_json TEXT,

            content_length INTEGER NOT NULL DEFAULT 0,

            content_hash TEXT,

            extracted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (page_id)
                REFERENCES pages(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_page_contents_page
        ON page_contents(page_id)
    """)

    register_schema_version(connection, 6)

    print("[MIGRATION] Schema version 6 verified.")


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def _initialize_once():
    """
    Execute base schema and all migrations in one transaction.

    Foreign keys are disabled only for the controlled table
    rebuild in migration 5, then restored before returning.
    """

    connection = get_connection()

    try:
        connection.execute("PRAGMA foreign_keys = OFF")

        journal_mode = connection.execute(
            "PRAGMA journal_mode = WAL"
        ).fetchone()[0]

        print(f"[DATABASE] Journal mode: {journal_mode}")

        connection.executescript(
            "BEGIN IMMEDIATE;\n" + SCHEMA
        )

        migrate_database(connection)
        migrate_v4(connection)
        migrate_v5(connection)
        migrate_v6(connection)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                analysis_run_id INTEGER PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE,
                format_version INTEGER NOT NULL DEFAULT 1,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        register_schema_version(connection, 7)
        connection.execute("""CREATE TABLE IF NOT EXISTS site_settings (
            project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
            settings_json TEXT NOT NULL
        )""")
        register_schema_version(connection, 8)
        connection.execute("""CREATE TABLE IF NOT EXISTS keyword_competitor_choices (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            domains_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(project_id, keyword)
        )""")
        register_schema_version(connection, 9)
        connection.execute("""CREATE TABLE IF NOT EXISTS analysis_stage_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
            stage_name TEXT NOT NULL CHECK(stage_name = 'competitors'),
            status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'partial', 'failed', 'cancelled')),
            format_version INTEGER NOT NULL DEFAULT 1 CHECK(format_version = 1),
            algorithm_version TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            result_json TEXT,
            error_type TEXT
        )""")
        connection.execute('CREATE INDEX IF NOT EXISTS idx_stage_source '
                           'ON analysis_stage_results(source_analysis_run_id, id)')
        register_schema_version(connection, 10)

        latest_version = connection.execute(
            "SELECT MAX(version) FROM schema_versions"
        ).fetchone()[0]

        if latest_version != CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Expected schema version {CURRENT_SCHEMA_VERSION}, "
                f"found {latest_version}"
            )

        required_tables = {
            "crawl_queue",
            "page_links",
            "crawl_events",
            "page_contents"
        }

        existing_tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        missing_tables = required_tables - existing_tables

        if missing_tables:
            raise RuntimeError(
                "Missing required tables: "
                + ", ".join(sorted(missing_tables))
            )

        analysis_columns = get_table_columns(
            connection,
            "analysis_runs"
        )

        required_analysis_columns = {
            "updated_at",
            "last_heartbeat_at",
            "completion_reason",
            "summary_json"
        }

        missing_analysis_columns = (
            required_analysis_columns - analysis_columns
        )

        if missing_analysis_columns:
            raise RuntimeError(
                "Missing analysis_runs columns: "
                + ", ".join(sorted(missing_analysis_columns))
            )

        page_content_columns = get_table_columns(
            connection,
            "page_contents"
        )

        required_page_content_columns = {
            "id",
            "page_id",
            "text_content",
            "h1_list_json",
            "h2_list_json",
            "h3_list_json",
            "content_length",
            "content_hash",
            "extracted_at"
        }

        missing_page_content_columns = (
            required_page_content_columns - page_content_columns
        )

        if missing_page_content_columns:
            raise RuntimeError(
                "Missing page_contents columns: "
                + ", ".join(sorted(missing_page_content_columns))
            )

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_errors:
            raise RuntimeError(
                "Foreign key validation failed: "
                f"{len(foreign_key_errors)} violation(s)."
            )

        connection.commit()

        connection.execute("PRAGMA foreign_keys = ON")

        foreign_keys_enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

        if foreign_keys_enabled != 1:
            raise RuntimeError(
                "Could not enable SQLite foreign key enforcement."
            )

        return journal_mode, latest_version

    except Exception:
        connection.rollback()

        try:
            connection.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error:
            pass

        raise

    finally:
        connection.close()


def initialize_database():
    """
    Initialize database with controlled retry for SQLite locks.
    """

    print("[DATABASE] Starting initialization...")

    for attempt in range(1, MIGRATION_MAX_RETRIES + 1):

        try:
            journal_mode, latest_version = _initialize_once()

            print(
                f"[DATABASE] Journal mode: {journal_mode}"
            )

            print(
                f"[DATABASE] Schema version: {latest_version}"
            )

            print(
                f"[MIGRATION] Schema version "
                f"{CURRENT_SCHEMA_VERSION} verified successfully."
            )

            print(
                f"[DATABASE] Database initialized: {DB_PATH}"
            )

            return

        except sqlite3.OperationalError as error:

            is_locked = (
                "database is locked" in str(error).lower()
                or "database is busy" in str(error).lower()
            )

            if not is_locked:
                raise

            if attempt >= MIGRATION_MAX_RETRIES:
                raise RuntimeError(
                    "SQLite database remained locked after "
                    f"{MIGRATION_MAX_RETRIES} attempts. "
                    "Close other applications using this database "
                    "and try again."
                ) from error

            delay = MIGRATION_RETRY_DELAY * attempt

            print(
                f"[DATABASE] Database is locked. "
                f"Retry {attempt}/{MIGRATION_MAX_RETRIES - 1} "
                f"in {delay} seconds..."
            )

            time.sleep(delay)


# =========================================================
# DATABASE INFORMATION
# =========================================================

def get_database_info():
    with database_connection() as connection:

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        versions = connection.execute(
            """
            SELECT version, applied_at
            FROM schema_versions
            ORDER BY version
            """
        ).fetchall()

        analysis_columns = get_table_columns(
            connection,
            "analysis_runs"
        )

        return {
            "database_path": str(DB_PATH),
            "tables": [row["name"] for row in tables],
            "analysis_run_columns": sorted(analysis_columns),
            "versions": [
                {
                    "version": row["version"],
                    "applied_at": row["applied_at"]
                }
                for row in versions
            ]
        }


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    initialize_database()

    info = get_database_info()

    print("\n========== DATABASE TABLES ==========")

    for table in info["tables"]:
        print(table)

    print("\n========== ANALYSIS RUN COLUMNS ==========")

    for column in info["analysis_run_columns"]:
        print(column)

    print("\n========== SCHEMA VERSIONS ==========")

    for version in info["versions"]:
        print(
            f"Version {version['version']} | "
            f"{version['applied_at']}"
        )
