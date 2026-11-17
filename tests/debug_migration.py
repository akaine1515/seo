
import database.connection as db

print("\n========== LOADED MODULE ==========\n")
print("Module file:", db.__file__)
print("Database path:", db.DB_PATH.resolve())

print("\n========== AVAILABLE MIGRATION ITEMS ==========\n")

print(
    "PAGE_COLUMNS_V2 exists:",
    hasattr(db, "PAGE_COLUMNS_V2")
)

print(
    "migrate_database exists:",
    hasattr(db, "migrate_database")
)

print(
    "initialize_database exists:",
    hasattr(db, "initialize_database")
)

print("\n========== MIGRATION SOURCE ==========\n")

if hasattr(db, "migrate_database"):
    import inspect
    print(inspect.getsource(db.migrate_database))

print("\n========== DATABASE STATE ==========\n")

with db.database_connection() as connection:

    versions = connection.execute(
        "SELECT * FROM schema_versions ORDER BY version"
    ).fetchall()

    print("Versions:", [dict(row) for row in versions])

    columns = connection.execute(
        "PRAGMA table_info(pages)"
    ).fetchall()

    print("Pages columns:", [row["name"] for row in columns])
