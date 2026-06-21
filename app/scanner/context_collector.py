import re
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_EXTENSIONS = {
    ".py",
    ".txt",
    ".md",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".js",
}


@dataclass
class CodeContext:
    included_files: list[str]
    missing_referenced_files: list[str] = field(default_factory=list)
    missing_optional_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    text: str = ""


def normalize_path(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def extract_file_paths_from_problem(problem: str) -> list[str]:
    paths: list[str] = []

    traceback_matches = re.findall(r'File "([^"]+)"', problem)

    for match in traceback_matches:
        if match.startswith("<") and match.endswith(">"):
            continue

        normalized = normalize_path(match)

        if normalized not in paths:
            paths.append(normalized)

    pytest_matches = re.findall(
        r"(?m)^([A-Za-z0-9_./\\-]+\.py):\d+",
        problem,
    )

    for match in pytest_matches:
        normalized = normalize_path(match)

        if normalized not in paths:
            paths.append(normalized)

    return paths


def to_project_relative_path(path_text: str, project_root: Path) -> str:
    normalized = normalize_path(path_text)
    path = Path(normalized)

    if path.is_absolute():
        try:
            return path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            return normalized

    return normalized


def is_safe_project_file(path: Path, project_root: Path) -> bool:
    try:
        path.resolve().relative_to(project_root.resolve())
        return True
    except ValueError:
        return False


def inspect_project_file(
    relative_path: str,
    project_root: Path,
    max_chars: int = 6000,
) -> tuple[str, str | None]:
    file_path = (project_root / relative_path).resolve()

    if not is_safe_project_file(file_path, project_root):
        return "skipped", None

    if not file_path.exists() or not file_path.is_file():
        return "missing", None

    if file_path.suffix not in ALLOWED_EXTENSIONS:
        return "skipped", None

    content = file_path.read_text(encoding="utf-8", errors="replace")

    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n... [file truncated] ..."

    return "included", content


def build_code_context(
    problem: str,
    extra_files: list[str] | None = None,
    max_files: int = 12,
    project_root: Path | None = None,
) -> CodeContext:
    root = project_root or DEFAULT_PROJECT_ROOT

    referenced_files = [
        to_project_relative_path(path, root)
        for path in extract_file_paths_from_problem(problem)
    ]

    optional_files: list[str] = []

    if extra_files:
        for file in extra_files:
            normalized = to_project_relative_path(file, root)
            if normalized not in optional_files:
                optional_files.append(normalized)

    included_files: list[str] = []
    missing_referenced_files: list[str] = []
    missing_optional_files: list[str] = []
    skipped_files: list[str] = []
    blocks: list[str] = []

    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []

    for file in referenced_files:
        candidates.append(("referenced", file))

    for file in optional_files:
        candidates.append(("optional", file))

    for source_type, relative_path in candidates:
        if relative_path in seen:
            continue

        seen.add(relative_path)

        if len(included_files) >= max_files:
            break

        status, content = inspect_project_file(relative_path, root)

        if status == "missing":
            if source_type == "referenced":
                missing_referenced_files.append(relative_path)
            else:
                missing_optional_files.append(relative_path)
            continue

        if status == "skipped":
            skipped_files.append(relative_path)
            continue

        if content is None:
            continue

        included_files.append(relative_path)

        blocks.append(
            f"--- FILE: {relative_path} ---\n"
            f"{content}\n"
            f"--- END FILE: {relative_path} ---"
        )

    return CodeContext(
        included_files=included_files,
        missing_referenced_files=missing_referenced_files,
        missing_optional_files=missing_optional_files,
        skipped_files=skipped_files,
        text="\n\n".join(blocks),
    )