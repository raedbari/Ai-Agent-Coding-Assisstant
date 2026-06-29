from __future__ import annotations

import subprocess
from pathlib import Path


def strip_markdown_code_fence(text: str) -> str:
    cleaned = text.strip()
    lines = cleaned.splitlines()

    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]

    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


def _normalize_diff_path(path_text: str) -> str:
    path = path_text.strip().split()[0]

    if path == "/dev/null":
        return path

    if path.startswith("a/") or path.startswith("b/"):
        path = path[2:]

    return path.replace("\\", "/")


def _extract_diff_paths(diff_text: str) -> set[str]:
    paths: set[str] = set()

    for line in diff_text.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            raw_path = line[4:].strip()
            path = _normalize_diff_path(raw_path)

            if path != "/dev/null":
                paths.add(path)

    return paths


def _project_prefix(project_root: Path, project_path: Path) -> str:
    root = project_root.resolve()
    project = project_path.resolve()

    try:
        prefix = project.relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"Project path is outside application root: {project_path}"
        ) from exc

    return prefix.rstrip("/") + "/"


def _validate_diff_paths(
    diff_text: str,
    project_root: Path,
    project_path: Path,
) -> list[str]:
    paths = _extract_diff_paths(diff_text)

    if not paths:
        raise ValueError("No file paths were found in the unified diff.")

    prefix = _project_prefix(
        project_root=project_root,
        project_path=project_path,
    )

    safe_paths: list[str] = []

    for path in sorted(paths):
        if path.startswith("/") or ".." in Path(path).parts:
            raise ValueError(f"Unsafe diff path: {path}")

        if not path.startswith(prefix):
            raise ValueError(
                f"Diff tries to modify a file outside the selected project: {path}"
            )

        absolute_path = (project_root / path).resolve()

        try:
            absolute_path.relative_to(project_root.resolve())
        except ValueError as exc:
            raise ValueError(f"Unsafe resolved diff path: {path}") from exc

        safe_paths.append(path)

    return safe_paths


def apply_sonar_project_diff(
    diff_text: str,
    project_root: Path,
    project_path: Path,
) -> dict:
    cleaned_diff = strip_markdown_code_fence(diff_text)

    if not cleaned_diff:
        return {
            "success": False,
            "status": "empty_diff",
            "message": "No diff was provided.",
            "applied_files": [],
            "diff": "",
        }

    changed_files = _validate_diff_paths(
        diff_text=cleaned_diff,
        project_root=project_root,
        project_path=project_path,
    )

    check_result = subprocess.run(
        ["git", "apply", "--check", "--recount", "--whitespace=nowarn", "-"],
        input=cleaned_diff,
        text=True,
        cwd=project_root,
        capture_output=True,
        timeout=30,
        check=False,
    )

    if check_result.returncode != 0:
        return {
            "success": False,
            "status": "check_failed",
            "message": check_result.stderr.strip() or "Patch check failed.",
            "applied_files": [],
            "diff": cleaned_diff,
        }

    apply_result = subprocess.run(
        ["git", "apply", "--recount", "--whitespace=nowarn", "-"],
        input=cleaned_diff,
        text=True,
        cwd=project_root,
        capture_output=True,
        timeout=30,
        check=False,
    )

    if apply_result.returncode != 0:
        return {
            "success": False,
            "status": "apply_failed",
            "message": apply_result.stderr.strip() or "Patch apply failed.",
            "applied_files": [],
            "diff": cleaned_diff,
        }

    return {
        "success": True,
        "status": "applied",
        "message": "Patch applied to the running demo workspace.",
        "applied_files": changed_files,
        "diff": cleaned_diff,
    }