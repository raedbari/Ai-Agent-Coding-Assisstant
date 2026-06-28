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
    "bug_issues": ProjectInfo(
        id="bug_issues",
        name="Bug Issues Demo",
        path=PROJECT_ROOT / "demo_projects" / "bug_issues",
        description="Demo files with logical bugs detected by SonarQube.",
    ),
    "security_issues": ProjectInfo(
        id="security_issues",
        name="Security Issues Demo",
        path=PROJECT_ROOT / "demo_projects" / "security_issues",
        description="Demo files with security issues detected by SonarQube.",
    ),
    "quality_issues": ProjectInfo(
        id="quality_issues",
        name="Quality Issues Demo",
        path=PROJECT_ROOT / "demo_projects" / "quality_issues",
        description="Demo files with maintainability and quality issues.",
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