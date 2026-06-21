from pathlib import Path


IGNORED_DIR_NAMES: set[str] = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".idea",
    ".vscode",
}

SENSITIVE_FILE_NAMES: set[str] = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

SENSITIVE_SUFFIXES: set[str] = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
}

DEPENDENCY_MANIFESTS: set[str] = {
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "package.json",
    "package-lock.json",
}

CONFIG_FILES: set[str] = {
    "ruff.toml",
    ".ruff.toml",
    "pytest.ini",
    "mypy.ini",
    "setup.cfg",
    "tox.ini",
}


def resolve_project_root(project_root: str) -> Path:
    root = Path(project_root).expanduser().resolve()

    if not root.exists():
        raise ValueError(f"Project root does not exist: {project_root}")

    if not root.is_dir():
        raise ValueError(f"Project root is not a directory: {project_root}")

    return root


def is_ignored_dir_name(name: str) -> bool:
    return name in IGNORED_DIR_NAMES


def is_sensitive_file(path: Path) -> bool:
    name = path.name

    if name in SENSITIVE_FILE_NAMES:
        return True

    if path.suffix in SENSITIVE_SUFFIXES:
        return True

    return False


def is_dependency_manifest(path: Path) -> bool:
    return path.name in DEPENDENCY_MANIFESTS


def is_config_file(path: Path) -> bool:
    return path.name in CONFIG_FILES


def is_python_source(path: Path) -> bool:
    return path.suffix == ".py"


def is_allowed_index_file(path: Path) -> bool:
    if is_sensitive_file(path):
        return False

    return (
        is_python_source(path)
        or is_dependency_manifest(path)
        or is_config_file(path)
    )


def safe_relative_path(root: Path, target: Path) -> str:
    resolved_target = target.resolve()

    try:
        relative = resolved_target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path is outside the project root") from exc

    return relative.as_posix()