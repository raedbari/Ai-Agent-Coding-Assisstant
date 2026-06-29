from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote


def _required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


def _run_git(
    args: list[str],
    cwd: Path,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def strip_markdown_code_fence(text: str) -> str:
    cleaned = text.strip()
    lines = cleaned.splitlines()

    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]

    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


def normalize_unified_diff_for_git_apply(diff_text: str) -> str:
    normalized_lines: list[str] = []
    inside_hunk = False

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            inside_hunk = False
            normalized_lines.append(line)
            continue

        if line.startswith("@@ "):
            inside_hunk = True
            normalized_lines.append(line)
            continue

        if inside_hunk:
            if line == "":
                normalized_lines.append(" ")
            elif line[0] in {" ", "+", "-", "\\"}:
                normalized_lines.append(line)
            else:
                normalized_lines.append(f" {line}")
            continue

        normalized_lines.append(line)

    return "\n".join(normalized_lines).strip() + "\n"


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

        safe_paths.append(path)

    return safe_paths


def _authenticated_repo_url(repo_url: str, token: str) -> str:
    if not repo_url.startswith("https://github.com/"):
        raise ValueError("Only https://github.com/... repository URLs are supported.")

    encoded_token = quote(token, safe="")

    return repo_url.replace(
        "https://github.com/",
        f"https://x-access-token:{encoded_token}@github.com/",
        1,
    )


def _clone_repo(workspace: Path) -> Path:
    token = _required_env("GITHUB_TOKEN")
    repo_url = _required_env("GITHUB_REPO_URL")
    branch = os.getenv("GITHUB_BRANCH", "main")

    clone_url = _authenticated_repo_url(
        repo_url=repo_url,
        token=token,
    )

    repo_dir = workspace / "repo"

    result = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            clone_url,
            str(repo_dir),
        ],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or "Failed to clone GitHub repository."
        )

    return repo_dir


def _try_apply_diff(repo_dir: Path, diff_text: str) -> tuple[bool, str]:
    check_result = _run_git(
        ["apply", "--check", "--recount", "--whitespace=nowarn", "-"],
        cwd=repo_dir,
        input_text=diff_text,
    )

    if check_result.returncode != 0:
        return False, check_result.stderr.strip() or "Patch check failed."

    apply_result = _run_git(
        ["apply", "--recount", "--whitespace=nowarn", "-"],
        cwd=repo_dir,
        input_text=diff_text,
    )

    if apply_result.returncode != 0:
        return False, apply_result.stderr.strip() or "Patch apply failed."

    return True, ""


def push_sonar_project_diff_to_github(
    diff_text: str,
    project_id: str,
    project_path: Path,
    project_root: Path,
) -> dict:
    raw_diff = strip_markdown_code_fence(diff_text)

    if not raw_diff:
        return {
            "success": False,
            "status": "empty_diff",
            "message": "No diff was provided.",
            "branch": os.getenv("GITHUB_BRANCH", "main"),
            "commit_sha": None,
            "applied_files": [],
            "diff": "",
        }

    normalized_diff = normalize_unified_diff_for_git_apply(raw_diff)

    changed_files = _validate_diff_paths(
        diff_text=normalized_diff,
        project_root=project_root,
        project_path=project_path,
    )

    branch = os.getenv("GITHUB_BRANCH", "main")
    author_name = os.getenv("GIT_AUTHOR_NAME", "AI Coding Assistant")
    author_email = os.getenv(
        "GIT_AUTHOR_EMAIL",
        "ai-coding-assistant@users.noreply.github.com",
    )

    with tempfile.TemporaryDirectory(prefix="ai-coding-github-") as temp_dir:
        workspace = Path(temp_dir)
        repo_dir = _clone_repo(workspace)

        _run_git(["config", "user.name", author_name], cwd=repo_dir)
        _run_git(["config", "user.email", author_email], cwd=repo_dir)

        applied, error_message = _try_apply_diff(
            repo_dir=repo_dir,
            diff_text=normalized_diff,
        )

        if not applied:
            return {
                "success": False,
                "status": "check_failed",
                "message": error_message,
                "branch": branch,
                "commit_sha": None,
                "applied_files": [],
                "diff": normalized_diff,
            }

        status_result = _run_git(["status", "--porcelain"], cwd=repo_dir)

        if not status_result.stdout.strip():
            return {
                "success": False,
                "status": "no_changes",
                "message": "Patch produced no repository changes.",
                "branch": branch,
                "commit_sha": None,
                "applied_files": changed_files,
                "diff": normalized_diff,
            }

        add_result = _run_git(["add", "--", *changed_files], cwd=repo_dir)

        if add_result.returncode != 0:
            return {
                "success": False,
                "status": "add_failed",
                "message": add_result.stderr.strip() or "Failed to stage files.",
                "branch": branch,
                "commit_sha": None,
                "applied_files": [],
                "diff": normalized_diff,
            }

        commit_message = f"fix: apply SonarQube repair for {project_id}"

        commit_result = _run_git(
            ["commit", "-m", commit_message],
            cwd=repo_dir,
        )

        if commit_result.returncode != 0:
            return {
                "success": False,
                "status": "commit_failed",
                "message": commit_result.stderr.strip()
                or "Failed to commit changes.",
                "branch": branch,
                "commit_sha": None,
                "applied_files": [],
                "diff": normalized_diff,
            }

        sha_result = _run_git(["rev-parse", "HEAD"], cwd=repo_dir)
        commit_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else None

        push_result = _run_git(["push", "origin", branch], cwd=repo_dir)

        if push_result.returncode != 0:
            return {
                "success": False,
                "status": "push_failed",
                "message": push_result.stderr.strip() or "Failed to push changes.",
                "branch": branch,
                "commit_sha": commit_sha,
                "applied_files": changed_files,
                "diff": normalized_diff,
            }

        return {
            "success": True,
            "status": "pushed",
            "message": "Patch committed and pushed to GitHub.",
            "branch": branch,
            "commit_sha": commit_sha,
            "applied_files": changed_files,
            "diff": normalized_diff,
        }