
from database.connection import database_connection


def inspect_pages_schema():
    with database_connection() as connection:

        print("\n========== DATABASE VERSIONS ==========\n")

        versions = connection.execute(
            "SELECT * FROM schema_versions ORDER BY version"
        ).fetchall()

        for version in versions:
            print(dict(version))

        print("\n========== PAGES TABLE COLUMNS ==========\n")

        columns = connection.execute(
            "PRAGMA table_info(pages)"
        ).fetchall()

        for column in columns:
            print(
                f"{column['name']} | "
                f"Type: {column['type']} | "
                f"Default: {column['dflt_value']}"
            )

        print("\n========== EXISTING PAGE RECORDS ==========\n")

        result = connection.execute(
            "SELECT COUNT(*) AS total FROM pages"
        ).fetchone()

        print(f"Existing pages: {result['total']}")


if __name__ == "__main__":
    inspect_pages_schema()
