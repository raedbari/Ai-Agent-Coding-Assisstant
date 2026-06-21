import os
from pathlib import Path

from app.scanner.models import FileRecord, FileRole
from app.scanner.path_guard import (
    is_allowed_index_file,
    is_config_file,
    is_dependency_manifest,
    is_ignored_dir_name,
    is_python_source,
    resolve_project_root,
    safe_relative_path,
)


def detect_file_role(path: Path) -> FileRole:
    if is_dependency_manifest(path):
        return FileRole.DEPENDENCY_MANIFEST

    if is_config_file(path):
        return FileRole.CONFIG_FILE

    if is_python_source(path):
        if path.name.startswith("test_") or "/tests/" in path.as_posix():
            return FileRole.TEST_FILE

        return FileRole.PYTHON_SOURCE

    return FileRole.CONFIG_FILE


def build_file_index(
    project_root: str,
    max_files: int = 5000,
    max_file_size_bytes: int = 1_000_000,
) -> list[FileRecord]:
    root = resolve_project_root(project_root)

    files: list[FileRecord] = []
    stack: list[Path] = [root]

    while stack:
        current_dir = stack.pop()

        try:
            entries = list(os.scandir(current_dir))
        except PermissionError:
            continue

        for entry in entries:
            entry_path = Path(entry.path)

            if entry.is_dir(follow_symlinks=False):
                if is_ignored_dir_name(entry.name):
                    continue

                stack.append(entry_path)
                continue

            if not entry.is_file(follow_symlinks=False):
                continue

            if not is_allowed_index_file(entry_path):
                continue

            try:
                stat_result = entry.stat(follow_symlinks=False)
            except OSError:
                continue

            if stat_result.st_size > max_file_size_bytes:
                continue

            relative_path = safe_relative_path(root, entry_path)

            files.append(
                FileRecord(
                    relative_path=relative_path,
                    suffix=entry_path.suffix,
                    size_bytes=stat_result.st_size,
                    role=detect_file_role(Path(relative_path)),
                )
            )

            if len(files) >= max_files:
                return files

    files.sort(key=lambda item: item.relative_path)
    return files