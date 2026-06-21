import ast
from dataclasses import dataclass
from pathlib import Path

from app.scanner.context_extractor import read_text_file
from app.scanner.models import IssueRecord
from app.scanner.path_guard import (
    is_allowed_index_file,
    resolve_project_root,
    safe_relative_path,
)


MAX_RELATED_CONTEXTS = 5
MAX_RELATED_CONTEXT_CHARS = 8000


@dataclass(frozen=True)
class ImportedSymbol:
    module: str
    name: str
    alias: str | None = None


def parse_python_source(path: Path) -> ast.AST | None:
    try:
        source = read_text_file(path)
        return ast.parse(source, filename=path.as_posix())
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None


def collect_imported_symbols(source_path: Path) -> list[ImportedSymbol]:
    tree = parse_python_source(source_path)

    if tree is None:
        return []

    imported_symbols: list[ImportedSymbol] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue

        if node.module is None:
            continue

        if node.level != 0:
            continue

        for alias in node.names:
            if alias.name == "*":
                continue

            imported_symbols.append(
                ImportedSymbol(
                    module=node.module,
                    name=alias.name,
                    alias=alias.asname,
                )
            )

    return imported_symbols


def module_name_to_candidate_paths(module_name: str) -> list[Path]:
    module_path = Path(*module_name.split("."))

    return [
        module_path.with_suffix(".py"),
        module_path / "__init__.py",
    ]


def resolve_local_module_path(
    project_root: Path,
    module_name: str,
) -> Path | None:
    for relative_candidate in module_name_to_candidate_paths(module_name):
        candidate = (project_root / relative_candidate).resolve()

        try:
            safe_relative_path(project_root, candidate)
        except ValueError:
            continue

        if candidate.exists() and candidate.is_file() and is_allowed_index_file(candidate):
            return candidate

    return None


def extract_definition_context(
    source_path: Path,
    symbol_name: str,
    max_chars: int = MAX_RELATED_CONTEXT_CHARS,
) -> str:
    try:
        source = read_text_file(source_path)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return ""

    lines = source.splitlines()
    tree = parse_python_source(source_path)

    if tree is None:
        return ""

    for node in ast.walk(tree):
        is_matching_function = isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ) and node.name == symbol_name

        is_matching_class = isinstance(node, ast.ClassDef) and node.name == symbol_name

        if not (is_matching_function or is_matching_class):
            continue

        start_line = max(1, getattr(node, "lineno", 1))
        end_line = getattr(node, "end_lineno", start_line)

        selected_lines: list[str] = []

        for line_number in range(start_line, end_line + 1):
            line_text = lines[line_number - 1]
            selected_lines.append(f"   {line_number}: {line_text}")

        context = "\n".join(selected_lines)

        if len(context) > max_chars:
            context = context[:max_chars] + "\n... related context truncated ..."

        return context

    return ""


def extract_file_head_context(
    source_path: Path,
    max_lines: int = 40,
    max_chars: int = MAX_RELATED_CONTEXT_CHARS,
) -> str:
    try:
        source = read_text_file(source_path)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return ""

    lines = source.splitlines()
    selected_lines: list[str] = []

    for line_number, line_text in enumerate(lines[:max_lines], start=1):
        selected_lines.append(f"   {line_number}: {line_text}")

    context = "\n".join(selected_lines)

    if len(context) > max_chars:
        context = context[:max_chars] + "\n... related context truncated ..."

    return context


def find_related_code_contexts(
    project_root: str,
    issue: IssueRecord,
) -> list[dict[str, object]]:
    root = resolve_project_root(project_root)

    if not issue.file_path:
        return []

    issue_file = (root / issue.file_path).resolve()

    try:
        safe_relative_path(root, issue_file)
    except ValueError:
        return []

    if not issue_file.exists() or not issue_file.is_file():
        return []

    imported_symbols = collect_imported_symbols(issue_file)

    related_contexts: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()

    for imported_symbol in imported_symbols:
        module_path = resolve_local_module_path(
            project_root=root,
            module_name=imported_symbol.module,
        )

        if module_path is None:
            continue

        relative_module_path = safe_relative_path(root, module_path)

        key = (relative_module_path, imported_symbol.name)

        if key in seen_keys:
            continue

        seen_keys.add(key)

        definition_context = extract_definition_context(
            source_path=module_path,
            symbol_name=imported_symbol.name,
        )

        if not definition_context:
            definition_context = extract_file_head_context(module_path)

        if not definition_context:
            continue

        related_contexts.append(
            {
                "file_path": relative_module_path,
                "symbol": imported_symbol.name,
                "module": imported_symbol.module,
                "context": definition_context,
                "reason": "imported_by_issue_file",
            }
        )

        if len(related_contexts) >= MAX_RELATED_CONTEXTS:
            break

    return related_contexts