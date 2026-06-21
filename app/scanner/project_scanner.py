from pathlib import Path


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
}

IGNORED_FILES = {
    ".env",
    ".env.local",
}

IMPORTANT_EXTENSIONS = {
    ".py",
    ".txt",
    ".md",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
}


def should_ignore_path(path: Path) -> bool:
    parts = set(path.parts)

    if parts.intersection(IGNORED_DIRS):
        return True

    if path.name in IGNORED_FILES:
        return True

    return False


def scan_project_files(
    project_root: Path | None = None,
    max_files: int = 120,
) -> list[str]:
    root = project_root or DEFAULT_PROJECT_ROOT

    files: list[str] = []

    for path in root.rglob("*"):
        if should_ignore_path(path):
            continue

        if not path.is_file():
            continue

        if path.suffix not in IMPORTANT_EXTENSIONS:
            continue

        relative_path = path.relative_to(root).as_posix()
        files.append(relative_path)

        if len(files) >= max_files:
            break

    return sorted(files)


def build_project_overview(project_root: Path | None = None) -> str:
    files = scan_project_files(project_root=project_root)

    lines = [
        "Project file overview:",
        "",
    ]

    for file in files:
        lines.append(f"- {file}")

    return "\n".join(lines)