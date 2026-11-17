
from urllib.parse import urlparse

from database.connection import initialize_database
from database.repository import (
    ProjectRepository,
    AnalysisRepository
)
from modules.crawler.engine import CrawlerEngine


def run_crawler_test():

    print("\n===================================")
    print(" SEO INTELLIGENCE - CRAWLER TEST")
    print("===================================\n")

    # Initialize database
    initialize_database()

    # Get website URL
    website_url = input(
        "Website URL: "
    ).strip()

    if not website_url:
        print("[ERROR] Website URL cannot be empty.")
        return

    if not website_url.startswith(("http://", "https://")):
        website_url = "https://" + website_url

    # Get maximum pages
    max_pages_input = input(
        "Maximum pages [default: 10]: "
    ).strip()

    try:
        max_pages = int(max_pages_input) if max_pages_input else 10

        if max_pages < 1:
            raise ValueError

    except ValueError:
        print("[ERROR] Maximum pages must be a positive integer.")
        return

    # Extract domain
    parsed_url = urlparse(website_url)
    domain = parsed_url.netloc.lower()

    if not domain:
        print("[ERROR] Invalid website URL.")
        return

    # Find existing project or create a new one
    existing_project = ProjectRepository.get_project_by_website(
        website_url
    )

    if existing_project:

        project_id = existing_project["id"]

        print(
            f"\n[INFO] Existing project found. "
            f"Project ID: {project_id}"
        )

    else:

        project_id = ProjectRepository.create_project(
            name=f"Crawler Test - {domain}",
            website_url=website_url,
            domain=domain,
            description="SEO Intelligence V2 crawler test"
        )

        print(
            f"\n[INFO] New project created. "
            f"Project ID: {project_id}"
        )

    # Create analysis run
    run_id = AnalysisRepository.create_analysis_run(
        project_id
    )

    print(f"[INFO] Analysis Run ID: {run_id}")

    # Start crawler
    try:

        crawler = CrawlerEngine(
            analysis_run_id=run_id,
            max_pages=max_pages
        )

        results = crawler.run(website_url)

        AnalysisRepository.finish_analysis_run(
            run_id,
            status="completed"
        )

        print("\n[TEST SUCCESS]")
        print("Crawler test completed successfully.")
        print(f"Results: {results}")

    except Exception as error:

        AnalysisRepository.finish_analysis_run(
            run_id,
            status="failed"
        )

        print("\n[TEST FAILED]")
        print(f"Error: {error}")

        raise


if __name__ == "__main__":
    run_crawler_test()
