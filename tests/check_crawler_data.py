
from database.connection import database_connection


def check_crawler_data():

    with database_connection() as connection:

        rows = connection.execute("""
            SELECT
                id,
                url,
                title,
                meta_description,
                h1,
                word_count,
                canonical_url,
                status_code
            FROM pages
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

        print("\n========== CRAWLER DATA CHECK ==========\n")

        for row in rows:
            print(f"ID: {row['id']}")
            print(f"URL: {row['url']}")
            print(f"Title: {row['title']}")
            print(f"Meta Description: {row['meta_description']}")
            print(f"H1: {row['h1']}")
            print(f"Word Count: {row['word_count']}")
            print(f"Canonical: {row['canonical_url']}")
            print(f"Status Code: {row['status_code']}")
            print("-" * 70)


if __name__ == "__main__":
    check_crawler_data()
