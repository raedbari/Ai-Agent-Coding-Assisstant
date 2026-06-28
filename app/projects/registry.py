from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ProjectInfo:
    id: str
    name: str
    path: Path
    description: str


ALLOWED_PROJECTS: dict[str, ProjectInfo] = {
    "broken_python": ProjectInfo(
        id="broken_python",
        name="Broken Python Demo",
        path=PROJECT_ROOT / "demo_projects" / "broken_python",
        description="Demo project with Python syntax errors",
    ),
    "ruff_issues": ProjectInfo(
        id="ruff_issues",
        name="Ruff Issues Demo",
        path=PROJECT_ROOT / "demo_projects" / "ruff_issues",
        description="Demo project with lint/style issues",
    ),
    "pytest_issues": ProjectInfo(
        id="pytest_issues",
        name="Pytest Issues Demo",
        path=PROJECT_ROOT / "demo_projects" / "pytest_issues",
        description="Demo project with failing tests",
    ),
    "sonar_demo": ProjectInfo(
        id="sonar_demo",
        name="SonarQube Demo",
        path=PROJECT_ROOT / "demo_projects",
        description=(
            "Demo project scanned by SonarQube with logic, security, "
            "and maintainability issues."
        ),
    ),
}


def list_projects() -> list[ProjectInfo]:
    return list(ALLOWED_PROJECTS.values())


def get_project(project_id: str) -> ProjectInfo:
    try:
        project = ALLOWED_PROJECTS[project_id]
    except KeyError as exc:
        raise ValueError(f"Unknown project id: {project_id}") from exc

    if not project.path.exists():
        raise FileNotFoundError(f"Project path does not exist: {project.path}")

    return project