import json
from database.connection import database_connection


# =========================================================
# CONSTANTS
# =========================================================

VALID_ANALYSIS_STATUSES = {
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
    "interrupted"
}

VALID_QUEUE_STATUSES = {
    "queued",
    "processing",
    "completed",
    "failed",
    "blocked",
    "skipped"
}

VALID_EVENT_SEVERITIES = {
    "critical",
    "high",
    "medium",
    "low",
    "info"
}


# =========================================================
# VALIDATION HELPERS
# =========================================================

def _validate_positive_id(value, field_name="ID"):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")


def _validate_non_empty(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")


def _dict_row(row):
    return dict(row) if row is not None else None


def _dict_rows(rows):
    return [dict(row) for row in rows]


# =========================================================
# PROJECT REPOSITORY
# =========================================================

class ProjectRepository:
    """
    Database operations related to projects.
    """

    @staticmethod
    def create_project(name, website_url, domain, description=""):
        _validate_non_empty(name, "Project name")
        _validate_non_empty(website_url, "Website URL")
        _validate_non_empty(domain, "Domain")

        name = name.strip()
        website_url = website_url.strip()
        domain = domain.strip()

        with database_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO projects (
                    name,
                    website_url,
                    domain,
                    description
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    website_url,
                    domain,
                    description
                )
            )

            return cursor.lastrowid

    @staticmethod
    def get_project_by_website(website_url):
        _validate_non_empty(website_url, "Website URL")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM projects
                WHERE website_url = ?
                LIMIT 1
                """,
                (website_url.strip(),)
            ).fetchone()

            return _dict_row(row)

    @staticmethod
    def get_project(project_id):
        _validate_positive_id(project_id, "Project ID")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM projects
                WHERE id = ?
                LIMIT 1
                """,
                (project_id,)
            ).fetchone()

            return _dict_row(row)

    @staticmethod
    def get_all_projects():
        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM projects
                ORDER BY id DESC
                """
            ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def update_project(
        project_id,
        name=None,
        website_url=None,
        domain=None,
        description=None
    ):
        _validate_positive_id(project_id, "Project ID")

        updates = {}
        allowed_fields = {
            "name": name,
            "website_url": website_url,
            "domain": domain,
            "description": description
        }

        for field, value in allowed_fields.items():
            if value is None:
                continue

            if field != "description":
                _validate_non_empty(value, field)

            updates[field] = (
                value.strip()
                if isinstance(value, str)
                else value
            )

        if not updates:
            return False

        assignments = ", ".join(
            f"{field} = ?"
            for field in updates
        )

        values = list(updates.values())

        values.append(project_id)

        with database_connection() as connection:
            cursor = connection.execute(
                f"""
                UPDATE projects
                SET
                    {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                values
            )

            return cursor.rowcount > 0

    @staticmethod
    def delete_project(project_id):
        _validate_positive_id(project_id, "Project ID")

        with database_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM projects
                WHERE id = ?
                """,
                (project_id,)
            )

            return cursor.rowcount > 0


# =========================================================
# ANALYSIS REPOSITORY
# =========================================================


class AnalysisRepository:
    """
    Database operations related to analysis runs.

    Lifecycle:
        pending -> running -> completed
                           -> failed
                           -> cancelled
                           -> interrupted

    Terminal statuses cannot be changed through finish_analysis_run.
    """

    TERMINAL_STATUSES = {
        "completed",
        "failed",
        "cancelled",
        "interrupted"
    }

    @staticmethod
    def create_analysis_run(project_id, max_pages=50):
        _validate_positive_id(project_id, "Project ID")

        if (
            isinstance(max_pages, bool)
            or not isinstance(max_pages, int)
            or max_pages <= 0
        ):
            raise ValueError("max_pages must be a positive integer.")

        with database_connection() as connection:
            project = connection.execute(
                """
                SELECT id
                FROM projects
                WHERE id = ?
                """,
                (project_id,)
            ).fetchone()

            if project is None:
                raise ValueError("Project does not exist.")

            cursor = connection.execute(
                """
                INSERT INTO analysis_runs (
                    project_id,
                    status,
                    max_pages,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?,
                    'pending',
                    ?,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """,
                (project_id, max_pages)
            )

            return cursor.lastrowid

    @staticmethod
    def start_analysis_run(run_id):
        """
        Transition a pending analysis to running.
        """

        _validate_positive_id(run_id, "Analysis run ID")

        with database_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE analysis_runs
                SET
                    status = 'running',
                    started_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    last_heartbeat_at = CURRENT_TIMESTAMP,
                    finished_at = NULL,
                    completion_reason = NULL,
                    error_message = NULL,
                    summary_json = NULL
                WHERE id = ?
                  AND status = 'pending'
                """,
                (run_id,)
            )

            return cursor.rowcount > 0

    @staticmethod
    def heartbeat_analysis_run(run_id):
        """
        Update the last activity timestamp of a running analysis.
        """

        _validate_positive_id(run_id, "Analysis run ID")

        with database_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE analysis_runs
                SET
                    last_heartbeat_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'running'
                """,
                (run_id,)
            )

            return cursor.rowcount > 0

    @staticmethod
    def _build_run_summary(connection, run_id):
        """
        Build a run summary using the existing database connection.

        This helper is intentionally connection-aware so that
        final summary creation and analysis completion can happen
        inside the same transaction.
        """

        page_stats = connection.execute(
            """
            SELECT
                COUNT(*) AS total_pages,
                SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END)
                    AS successful_pages,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END)
                    AS client_or_server_errors,
                SUM(CASE WHEN is_indexable = 1 THEN 1 ELSE 0 END)
                    AS indexable_pages,
                SUM(CASE WHEN is_indexable = 0 THEN 1 ELSE 0 END)
                    AS non_indexable_pages,
                SUM(COALESCE(word_count, 0)) AS total_words
            FROM pages
            WHERE analysis_run_id = ?
            """,
            (run_id,)
        ).fetchone()

        queue_rows = connection.execute(
            """
            SELECT
                status,
                COUNT(*) AS total
            FROM crawl_queue
            WHERE analysis_run_id = ?
            GROUP BY status
            """,
            (run_id,)
        ).fetchall()

        link_stats = connection.execute(
            """
            SELECT
                COUNT(*) AS total_links,
                SUM(CASE WHEN is_internal = 1 THEN 1 ELSE 0 END)
                    AS internal_links,
                SUM(CASE WHEN is_internal = 0 THEN 1 ELSE 0 END)
                    AS external_links
            FROM page_links
            WHERE analysis_run_id = ?
            """,
            (run_id,)
        ).fetchone()

        queue = {
            status: 0
            for status in VALID_QUEUE_STATUSES
        }

        for row in queue_rows:
            queue[row["status"]] = row["total"]

        return {
            "analysis_run_id": run_id,
            "pages": _dict_row(page_stats),
            "queue": queue,
            "links": _dict_row(link_stats)
        }

    @staticmethod
    def finish_analysis_run(
        run_id,
        status="completed",
        error_message=None,
        completion_reason=None,
        summary=None
    ):
        """
        Finish a running analysis.

        Only running analyses can be finished.
        Terminal statuses cannot be overwritten.

        If summary is not supplied, it is generated automatically.
        """

        _validate_positive_id(run_id, "Analysis run ID")

        if status not in AnalysisRepository.TERMINAL_STATUSES:
            raise ValueError(
                f"Invalid terminal analysis status: {status}"
            )

        if error_message is not None and not isinstance(error_message, str):
            raise TypeError("error_message must be a string or None.")

        if (
            completion_reason is not None
            and not isinstance(completion_reason, str)
        ):
            raise TypeError(
                "completion_reason must be a string or None."
            )

        if summary is not None and not isinstance(summary, dict):
            raise TypeError("summary must be a dictionary or None.")

        with database_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            run = connection.execute(
                """
                SELECT id, status
                FROM analysis_runs
                WHERE id = ?
                """,
                (run_id,)
            ).fetchone()

            if run is None or run["status"] != "running":
                return False

            final_summary = (
                summary
                if summary is not None
                else AnalysisRepository._build_run_summary(
                    connection,
                    run_id
                )
            )

            summary_json = json.dumps(
                final_summary,
                ensure_ascii=False,
                default=str
            )

            cursor = connection.execute(
                """
                UPDATE analysis_runs
                SET
                    status = ?,
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    last_heartbeat_at = CURRENT_TIMESTAMP,
                    completion_reason = ?,
                    error_message = ?,
                    summary_json = ?
                WHERE id = ?
                  AND status = 'running'
                """,
                (
                    status,
                    completion_reason,
                    error_message,
                    summary_json,
                    run_id
                )
            )

            return cursor.rowcount > 0

    @staticmethod
    def get_analysis_run(run_id):
        _validate_positive_id(run_id, "Analysis run ID")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM analysis_runs
                WHERE id = ?
                LIMIT 1
                """,
                (run_id,)
            ).fetchone()

            return _dict_row(row)

    @staticmethod
    def get_project_analysis_runs(project_id):
        _validate_positive_id(project_id, "Project ID")

        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM analysis_runs
                WHERE project_id = ?
                ORDER BY id DESC
                """,
                (project_id,)
            ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def get_latest_analysis_run(project_id):
        _validate_positive_id(project_id, "Project ID")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM analysis_runs
                WHERE project_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (project_id,)
            ).fetchone()

            return _dict_row(row)

    @staticmethod
    def get_running_analysis_runs():
        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM analysis_runs
                WHERE status = 'running'
                ORDER BY started_at DESC
                """
            ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def get_pending_analysis_runs():
        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM analysis_runs
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def get_interrupted_analysis_runs():
        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM analysis_runs
                WHERE status = 'interrupted'
                ORDER BY finished_at DESC
                """
            ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def mark_stale_analysis_runs_interrupted(timeout_minutes=30):
        """
        Mark stale running analyses as interrupted.

        An analysis is stale when its latest heartbeat/activity
        timestamp is older than timeout_minutes.

        This method should be called by startup recovery logic,
        not repeatedly by the crawler during normal execution.
        """

        if (
            isinstance(timeout_minutes, bool)
            or not isinstance(timeout_minutes, int)
            or timeout_minutes <= 0
        ):
            raise ValueError(
                "timeout_minutes must be a positive integer."
            )

        modifier = f"-{timeout_minutes} minutes"

        with database_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            stale_runs = connection.execute(
                """
                SELECT id
                FROM analysis_runs
                WHERE status = 'running'
                  AND COALESCE(
                      last_heartbeat_at,
                      updated_at,
                      started_at,
                      created_at
                  ) < datetime('now', ?)
                ORDER BY id
                """,
                (modifier,)
            ).fetchall()

            interrupted_count = 0

            for row in stale_runs:
                run_id = row["id"]

                summary = AnalysisRepository._build_run_summary(
                    connection,
                    run_id
                )

                summary_json = json.dumps(
                    summary,
                    ensure_ascii=False,
                    default=str
                )

                cursor = connection.execute(
                    """
                    UPDATE analysis_runs
                    SET
                        status = 'interrupted',
                        finished_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP,
                        completion_reason = 'stale_heartbeat_timeout',
                        error_message = COALESCE(
                            error_message,
                            'Analysis interrupted because no heartbeat was received.'
                        ),
                        summary_json = ?
                    WHERE id = ?
                      AND status = 'running'
                    """,
                    (summary_json, run_id)
                )

                interrupted_count += max(cursor.rowcount, 0)

            return interrupted_count


# =========================================================
# PAGE REPOSITORY
# =========================================================

class PageRepository:
    """
    Database operations related to crawled pages.
    """

    @staticmethod
    def save_page(analysis_run_id, page_data):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        if not isinstance(page_data, dict):
            raise TypeError("page_data must be a dictionary.")

        _validate_non_empty(
            page_data.get("url"),
            "Page URL"
        )

        columns = [
            "analysis_run_id",
            "url",
            "canonical_url",
            "title",
            "meta_description",
            "h1",
            "status_code",
            "content_type",
            "word_count",
            "depth",
            "is_indexable",
            "robots_directive",
            "canonical_status",
            "content_hash",
            "title_length",
            "meta_description_length",
            "h1_count",
            "h2_count",
            "h3_count",
            "headings_json",
            "image_count",
            "images_without_alt",
            "internal_links_count",
            "external_links_count",
            "x_robots_tag",
            "is_nofollow",
            "parent_url",
            "final_url",
            "redirect_chain_json",
            "crawl_status",
            "crawl_error",
            "duplicate_of_url",
            "duplicate_type",
            "unique_internal_links_count",
            "unique_external_links_count",
            "nofollow_links_count"
        ]

        values = [
            analysis_run_id,
            page_data.get("url"),
            page_data.get("canonical_url"),
            page_data.get("title"),
            page_data.get("meta_description"),
            page_data.get("h1"),
            page_data.get("status_code"),
            page_data.get("content_type"),
            page_data.get("word_count", 0),
            page_data.get("depth", 0),
            page_data.get("is_indexable", 1),
            page_data.get("robots_directive"),
            page_data.get("canonical_status"),
            page_data.get("content_hash"),
            page_data.get("title_length", 0),
            page_data.get("meta_description_length", 0),
            page_data.get("h1_count", 0),
            page_data.get("h2_count", 0),
            page_data.get("h3_count", 0),
            page_data.get("headings_json"),
            page_data.get("image_count", 0),
            page_data.get("images_without_alt", 0),
            page_data.get("internal_links_count", 0),
            page_data.get("external_links_count", 0),
            page_data.get("x_robots_tag"),
            page_data.get("is_nofollow", 0),
            page_data.get("parent_url"),
            page_data.get("final_url"),
            page_data.get("redirect_chain_json"),
            page_data.get("crawl_status", "success"),
            page_data.get("crawl_error"),
            page_data.get("duplicate_of_url"),
            page_data.get("duplicate_type"),
            page_data.get("unique_internal_links_count", 0),
            page_data.get("unique_external_links_count", 0),
            page_data.get("nofollow_links_count", 0)
        ]

        placeholders = ", ".join("?" for _ in columns)

        update_columns = [
            column
            for column in columns
            if column not in {"analysis_run_id", "url"}
        ]

        update_clause = ", ".join(
            f"{column} = excluded.{column}"
            for column in update_columns
        )

        with database_connection() as connection:
            cursor = connection.execute(
                f"""
                INSERT INTO pages ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (analysis_run_id, url)
                DO UPDATE SET {update_clause}
                """,
                values
            )

            row = connection.execute(
                """
                SELECT id
                FROM pages
                WHERE analysis_run_id = ?
                  AND url = ?
                """,
                (
                    analysis_run_id,
                    page_data["url"]
                )
            ).fetchone()

            return row["id"] if row else cursor.lastrowid

    @staticmethod
    def get_page(page_id):
        _validate_positive_id(page_id, "Page ID")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM pages
                WHERE id = ?
                """,
                (page_id,)
            ).fetchone()

            return _dict_row(row)

    @staticmethod
    def get_page_by_url(analysis_run_id, url):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )
        _validate_non_empty(url, "URL")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM pages
                WHERE analysis_run_id = ?
                  AND url = ?
                LIMIT 1
                """,
                (analysis_run_id, url)
            ).fetchone()

            return _dict_row(row)

    @staticmethod
    def get_run_pages(analysis_run_id, limit=None, offset=0):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        if limit is not None and (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit <= 0
        ):
            raise ValueError("limit must be a positive integer.")

        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer.")

        with database_connection() as connection:
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM pages
                    WHERE analysis_run_id = ?
                    ORDER BY id
                    """,
                    (analysis_run_id,)
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM pages
                    WHERE analysis_run_id = ?
                    ORDER BY id
                    LIMIT ? OFFSET ?
                    """,
                    (analysis_run_id, limit, offset)
                ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def count_run_pages(analysis_run_id):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM pages
                WHERE analysis_run_id = ?
                """,
                (analysis_run_id,)
            ).fetchone()

            return row["total"]


# =========================================================
# PAGE CONTENT REPOSITORY
# =========================================================

class PageContentRepository:
    """
    Database operations related to extracted page contents and headings.
    """

    @staticmethod
    def _validate_and_clean_headings(headings, field_name):
        """
        Validate that headings is None or a list of strings,
        and return a cleaned list of non-empty strings.
        """
        if headings is None:
            return []

        if not isinstance(headings, list):
            raise TypeError(f"{field_name} must be a list or None.")

        cleaned_headings = []
        for index, item in enumerate(headings):
            if not isinstance(item, str):
                raise TypeError(
                    f"Item at index {index} in {field_name} must be a string."
                )
            stripped = item.strip()
            if stripped:
                cleaned_headings.append(stripped)

        return cleaned_headings

    @staticmethod
    def save_page_content(
        page_id,
        text_content,
        h1_list=None,
        h2_list=None,
        h3_list=None,
        content_hash=None
    ):
        """
        Save or update extracted text content and headings for a crawled page.
        """
        _validate_positive_id(page_id, "Page ID")

        if text_content is None:
            text_content = ""
        elif not isinstance(text_content, str):
            raise TypeError("text_content must be a string.")

        if content_hash is not None and not isinstance(content_hash, str):
            raise TypeError("content_hash must be a string or None.")

        if isinstance(content_hash, str):
            content_hash = content_hash.strip() or None

        cleaned_h1 = PageContentRepository._validate_and_clean_headings(
            h1_list, "h1_list"
        )
        cleaned_h2 = PageContentRepository._validate_and_clean_headings(
            h2_list, "h2_list"
        )
        cleaned_h3 = PageContentRepository._validate_and_clean_headings(
            h3_list, "h3_list"
        )

        h1_json = json.dumps(cleaned_h1, ensure_ascii=False)
        h2_json = json.dumps(cleaned_h2, ensure_ascii=False)
        h3_json = json.dumps(cleaned_h3, ensure_ascii=False)
        content_length = len(text_content)

        with database_connection() as connection:
            page = connection.execute(
                """
                SELECT id
                FROM pages
                WHERE id = ?
                """,
                (page_id,)
            ).fetchone()

            if page is None:
                raise ValueError("Page does not exist.")

            cursor = connection.execute(
                """
                INSERT INTO page_contents (
                    page_id,
                    text_content,
                    h1_list_json,
                    h2_list_json,
                    h3_list_json,
                    content_length,
                    content_hash,
                    extracted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (page_id)
                DO UPDATE SET
                    text_content = excluded.text_content,
                    h1_list_json = excluded.h1_list_json,
                    h2_list_json = excluded.h2_list_json,
                    h3_list_json = excluded.h3_list_json,
                    content_length = excluded.content_length,
                    content_hash = excluded.content_hash,
                    extracted_at = CURRENT_TIMESTAMP
                """,
                (
                    page_id,
                    text_content,
                    h1_json,
                    h2_json,
                    h3_json,
                    content_length,
                    content_hash
                )
            )

            row = connection.execute(
                """
                SELECT id
                FROM page_contents
                WHERE page_id = ?
                """,
                (page_id,)
            ).fetchone()

            return row["id"] if row else cursor.lastrowid

    @staticmethod
    def _deserialize_content_row(row):
        """
        Convert a page_contents row into a dictionary with parsed heading lists.
        """
        if row is None:
            return None

        data = dict(row)
        data["h1_list"] = json.loads(data.get("h1_list_json") or "[]")
        data["h2_list"] = json.loads(data.get("h2_list_json") or "[]")
        data["h3_list"] = json.loads(data.get("h3_list_json") or "[]")
        return data

    @staticmethod
    def get_page_content(page_id):
        """
        Retrieve extracted content and headings for a specific page ID.
        """
        _validate_positive_id(page_id, "Page ID")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM page_contents
                WHERE page_id = ?
                LIMIT 1
                """,
                (page_id,)
            ).fetchone()

            return PageContentRepository._deserialize_content_row(row)

    @staticmethod
    def get_run_contents(analysis_run_id, non_empty_only=True):
        """
        Retrieve all extracted page contents belonging to an analysis run.
        """
        _validate_positive_id(analysis_run_id, "Analysis run ID")

        if not isinstance(non_empty_only, bool):
            raise TypeError("non_empty_only must be a boolean.")

        with database_connection() as connection:
            if non_empty_only:
                rows = connection.execute(
                    """
                    SELECT
                        pc.*,
                        p.analysis_run_id,
                        p.url,
                        p.title,
                        p.meta_description,
                        p.word_count,
                        p.is_indexable
                    FROM page_contents pc
                    INNER JOIN pages p
                        ON p.id = pc.page_id
                    WHERE p.analysis_run_id = ?
                      AND pc.text_content IS NOT NULL
                      AND TRIM(pc.text_content) != ''
                    ORDER BY p.id
                    """,
                    (analysis_run_id,)
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        pc.*,
                        p.analysis_run_id,
                        p.url,
                        p.title,
                        p.meta_description,
                        p.word_count,
                        p.is_indexable
                    FROM page_contents pc
                    INNER JOIN pages p
                        ON p.id = pc.page_id
                    WHERE p.analysis_run_id = ?
                    ORDER BY p.id
                    """,
                    (analysis_run_id,)
                ).fetchall()

            return [
                PageContentRepository._deserialize_content_row(row)
                for row in rows
            ]

    @staticmethod
    def count_run_contents(analysis_run_id):
        """
        Count stored page content records for an analysis run.
        """
        _validate_positive_id(analysis_run_id, "Analysis run ID")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM page_contents pc
                INNER JOIN pages p
                    ON p.id = pc.page_id
                WHERE p.analysis_run_id = ?
                """,
                (analysis_run_id,)
            ).fetchone()

            return row["total"]


# =========================================================
# CRAWL QUEUE REPOSITORY
# =========================================================

class CrawlQueueRepository:
    """
    Persistent URL queue operations.
    """

    @staticmethod
    def add_url(
        analysis_run_id,
        url,
        normalized_url,
        depth=0,
        parent_url=None,
        discovered_from=None,
        priority=0
    ):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )
        _validate_non_empty(url, "URL")
        _validate_non_empty(normalized_url, "Normalized URL")

        if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
            raise ValueError("depth must be a non-negative integer.")

        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError("priority must be an integer.")

        with database_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO crawl_queue (
                    analysis_run_id,
                    url,
                    normalized_url,
                    depth,
                    parent_url,
                    discovered_from,
                    priority,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'queued')
                ON CONFLICT (analysis_run_id, normalized_url)
                DO NOTHING
                """,
                (
                    analysis_run_id,
                    url.strip(),
                    normalized_url.strip(),
                    depth,
                    parent_url,
                    discovered_from,
                    priority
                )
            )

            if cursor.rowcount == 0:
                row = connection.execute(
                    """
                    SELECT id
                    FROM crawl_queue
                    WHERE analysis_run_id = ?
                      AND normalized_url = ?
                    """,
                    (analysis_run_id, normalized_url.strip())
                ).fetchone()

                return row["id"] if row else None

            return cursor.lastrowid

    @staticmethod
    def add_urls(analysis_run_id, urls):
        """
        Add multiple URL dictionaries in one transaction.

        Each item may contain:
        url, normalized_url, depth, parent_url,
        discovered_from and priority.
        """

        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        if not isinstance(urls, (list, tuple)):
            raise TypeError("urls must be a list or tuple.")

        inserted = 0

        with database_connection() as connection:
            for item in urls:
                if not isinstance(item, dict):
                    raise TypeError("Each URL item must be a dictionary.")

                url = item.get("url")
                normalized_url = item.get("normalized_url")

                _validate_non_empty(url, "URL")
                _validate_non_empty(
                    normalized_url,
                    "Normalized URL"
                )

                cursor = connection.execute(
                    """
                    INSERT INTO crawl_queue (
                        analysis_run_id,
                        url,
                        normalized_url,
                        depth,
                        parent_url,
                        discovered_from,
                        priority
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (analysis_run_id, normalized_url)
                    DO NOTHING
                    """,
                    (
                        analysis_run_id,
                        url.strip(),
                        normalized_url.strip(),
                        item.get("depth", 0),
                        item.get("parent_url"),
                        item.get("discovered_from"),
                        item.get("priority", 0)
                    )
                )

                inserted += max(cursor.rowcount, 0)

        return inserted

    @staticmethod
    def get_next_url(analysis_run_id):
        """
        Atomically claim the next queued URL.
        """

        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        with database_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT *
                FROM crawl_queue
                WHERE analysis_run_id = ?
                  AND status = 'queued'
                ORDER BY priority DESC, depth ASC, id ASC
                LIMIT 1
                """,
                (analysis_run_id,)
            ).fetchone()

            if row is None:
                return None

            cursor = connection.execute(
                """
                UPDATE crawl_queue
                SET
                    status = 'processing',
                    attempt_count = attempt_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'queued'
                """,
                (row["id"],)
            )

            if cursor.rowcount == 0:
                return None

            result = dict(row)
            result["status"] = "processing"
            result["attempt_count"] = row["attempt_count"] + 1

            return result

    @staticmethod
    def update_status(
        queue_id,
        status,
        last_error=None
    ):
        _validate_positive_id(queue_id, "Queue ID")

        if status not in VALID_QUEUE_STATUSES:
            raise ValueError(f"Invalid queue status: {status}")

        with database_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE crawl_queue
                SET
                    status = ?,
                    last_error = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    processed_at = CASE
                        WHEN ? IN (
                            'completed', 'failed', 'blocked', 'skipped'
                        )
                        THEN CURRENT_TIMESTAMP
                        ELSE NULL
                    END
                WHERE id = ?
                """,
                (
                    status,
                    last_error,
                    status,
                    queue_id
                )
            )

            return cursor.rowcount > 0

    @staticmethod
    def get_queue_stats(analysis_run_id):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    status,
                    COUNT(*) AS total
                FROM crawl_queue
                WHERE analysis_run_id = ?
                GROUP BY status
                """,
                (analysis_run_id,)
            ).fetchall()

            stats = {
                status: 0
                for status in VALID_QUEUE_STATUSES
            }

            for row in rows:
                stats[row["status"]] = row["total"]

            stats["total"] = sum(
                stats[status]
                for status in VALID_QUEUE_STATUSES
            )

            return stats

    @staticmethod
    def recover_processing_items(analysis_run_id=None):
        with database_connection() as connection:
            if analysis_run_id is None:
                cursor = connection.execute(
                    """
                    UPDATE crawl_queue
                    SET
                        status = 'queued',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE status = 'processing'
                    """
                )
            else:
                _validate_positive_id(
                    analysis_run_id,
                    "Analysis run ID"
                )

                cursor = connection.execute(
                    """
                    UPDATE crawl_queue
                    SET
                        status = 'queued',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE analysis_run_id = ?
                      AND status = 'processing'
                    """,
                    (analysis_run_id,)
                )

            return cursor.rowcount

    @staticmethod
    def get_pending_urls(analysis_run_id, limit=100):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer.")

        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM crawl_queue
                WHERE analysis_run_id = ?
                  AND status = 'queued'
                ORDER BY priority DESC, depth ASC, id ASC
                LIMIT ?
                """,
                (analysis_run_id, limit)
            ).fetchall()

            return _dict_rows(rows)


# =========================================================
# PAGE LINKS REPOSITORY
# =========================================================

class PageLinkRepository:
    """
    Store and retrieve individual links extracted from pages.
    """

    @staticmethod
    def save_links(analysis_run_id, source_page_id, links):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )
        _validate_positive_id(
            source_page_id,
            "Source page ID"
        )

        if not isinstance(links, (list, tuple)):
            raise TypeError("links must be a list or tuple.")

        with database_connection() as connection:
            page = connection.execute(
                """
                SELECT id
                FROM pages
                WHERE id = ?
                  AND analysis_run_id = ?
                """,
                (source_page_id, analysis_run_id)
            ).fetchone()

            if page is None:
                raise ValueError(
                    "Source page does not belong to this analysis run."
                )

            # Replace previously extracted links for this page.
            connection.execute(
                """
                DELETE FROM page_links
                WHERE source_page_id = ?
                """,
                (source_page_id,)
            )

            for position, link in enumerate(links):
                if not isinstance(link, dict):
                    raise TypeError("Each link must be a dictionary.")

                target_url = link.get("target_url")

                _validate_non_empty(
                    target_url,
                    "Link target URL"
                )

                connection.execute(
                    """
                    INSERT INTO page_links (
                        analysis_run_id,
                        source_page_id,
                        target_page_id,
                        source_url,
                        target_url,
                        anchor_text,
                        rel,
                        is_internal,
                        link_type,
                        link_position
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_run_id,
                        source_page_id,
                        link.get("target_page_id"),
                        link.get("source_url", ""),
                        target_url.strip(),
                        link.get("anchor_text"),
                        link.get("rel"),
                        int(bool(link.get("is_internal", True))),
                        link.get("link_type", "html"),
                        link.get("link_position", position)
                    )
                )

            return len(links)

    @staticmethod
    def get_page_links(source_page_id):
        _validate_positive_id(
            source_page_id,
            "Source page ID"
        )

        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM page_links
                WHERE source_page_id = ?
                ORDER BY link_position
                """,
                (source_page_id,)
            ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def get_run_links(analysis_run_id, internal_only=None):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        with database_connection() as connection:
            if internal_only is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM page_links
                    WHERE analysis_run_id = ?
                    ORDER BY id
                    """,
                    (analysis_run_id,)
                ).fetchall()

            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM page_links
                    WHERE analysis_run_id = ?
                      AND is_internal = ?
                    ORDER BY id
                    """,
                    (
                        analysis_run_id,
                        int(bool(internal_only))
                    )
                ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def count_inbound_links(analysis_run_id, target_url):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )
        _validate_non_empty(target_url, "Target URL")

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM page_links
                WHERE analysis_run_id = ?
                  AND target_url = ?
                  AND is_internal = 1
                """,
                (analysis_run_id, target_url)
            ).fetchone()

            return row["total"]

    @staticmethod
    def get_broken_link_candidates(analysis_run_id):
        """
        Find internal links whose target URL has no crawled page.

        This is a candidate list, not a confirmed HTTP broken-link list.
        """

        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    pl.target_url,
                    COUNT(*) AS inbound_count,
                    GROUP_CONCAT(DISTINCT p.url) AS source_urls
                FROM page_links pl
                JOIN pages p
                    ON p.id = pl.source_page_id
                LEFT JOIN pages target
                    ON target.analysis_run_id = pl.analysis_run_id
                   AND target.url = pl.target_url
                WHERE pl.analysis_run_id = ?
                  AND pl.is_internal = 1
                  AND target.id IS NULL
                GROUP BY pl.target_url
                ORDER BY inbound_count DESC
                """,
                (analysis_run_id,)
            ).fetchall()

            return _dict_rows(rows)


# =========================================================
# CRAWL EVENT REPOSITORY
# =========================================================

class CrawlEventRepository:
    """
    Record crawler events, warnings and errors.
    """

    @staticmethod
    def log_event(
        analysis_run_id,
        event_type,
        message=None,
        url=None,
        severity="info",
        details_json=None
    ):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )
        _validate_non_empty(event_type, "Event type")

        if severity not in VALID_EVENT_SEVERITIES:
            raise ValueError(
                f"Invalid event severity: {severity}"
            )

        with database_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO crawl_events (
                    analysis_run_id,
                    url,
                    event_type,
                    severity,
                    message,
                    details_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_run_id,
                    url,
                    event_type.strip(),
                    severity,
                    message,
                    details_json
                )
            )

            return cursor.lastrowid

    @staticmethod
    def get_run_events(
        analysis_run_id,
        severity=None,
        limit=500
    ):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer.")

        with database_connection() as connection:
            if severity is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM crawl_events
                    WHERE analysis_run_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (analysis_run_id, limit)
                ).fetchall()

            else:
                if severity not in VALID_EVENT_SEVERITIES:
                    raise ValueError(
                        f"Invalid severity: {severity}"
                    )

                rows = connection.execute(
                    """
                    SELECT *
                    FROM crawl_events
                    WHERE analysis_run_id = ?
                      AND severity = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (
                        analysis_run_id,
                        severity,
                        limit
                    )
                ).fetchall()

            return _dict_rows(rows)

    @staticmethod
    def count_run_events(analysis_run_id):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        with database_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM crawl_events
                WHERE analysis_run_id = ?
                """,
                (analysis_run_id,)
            ).fetchone()

            return row["total"]


# =========================================================
# CRAWL SUMMARY REPOSITORY
# =========================================================


class CrawlSummaryRepository:
    """
    Provide aggregated crawler statistics.
    """

    @staticmethod
    def get_run_summary(analysis_run_id):
        _validate_positive_id(
            analysis_run_id,
            "Analysis run ID"
        )

        with database_connection() as connection:
            return AnalysisRepository._build_run_summary(
                connection,
                analysis_run_id
            )