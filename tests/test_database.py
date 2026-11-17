
from database.connection import initialize_database
from database.repository import ProjectRepository, AnalysisRepository


def run_test():
    # Initialize database
    initialize_database()

    # Create a temporary test project
    project_id = ProjectRepository.create_project(
        name="SEO Test Project",
        website_url="https://example.com",
        domain="example.com",
        description="Database connection test"
    )

    print("Project created:", project_id)

    # Create an analysis run
    run_id = AnalysisRepository.create_run(
        project_id=project_id,
        max_pages=30
    )

    print("Analysis run created:", run_id)

    # Finish the test run
    AnalysisRepository.finish_run(
        run_id=run_id,
        status="completed"
    )

    # Verify saved data
    project = ProjectRepository.get_project(project_id)
    runs = AnalysisRepository.get_project_runs(project_id)

    assert project is not None
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"

    # Remove test data
    ProjectRepository.delete_project(project_id)

    print("\nAll database tests passed successfully!")


if __name__ == "__main__":
    run_test()
