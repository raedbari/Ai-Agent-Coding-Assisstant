import ast
import difflib
import re
from pathlib import Path
from typing import Any


SUPPORTED_CHANGE_TYPES = {"modify", "dependency", "create"}


def resolve_project_file(project_root: Path, file_path: str) -> Path:
    target = (project_root / file_path).resolve()

    try:
        target.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Unsafe file path outside project: {file_path}") from exc

    return target


def parse_replace_instruction(instructions: str) -> tuple[str, str] | None:
    patterns = [
        # Replace 'old' with 'new'
        r"Replace\s+'([^']+)'\s+with\s+'([^']+)'",
        r'Replace\s+"([^"]+)"\s+with\s+"([^"]+)"',
        r"Replace\s+`([^`]+)`\s+with\s+`([^`]+)`",

        # change 'old' to 'new'
        r"change\s+'([^']+)'\s+to\s+'([^']+)'",
        r'change\s+"([^"]+)"\s+to\s+"([^"]+)"',
        r"change\s+`([^`]+)`\s+to\s+`([^`]+)`",

        # Change X -> Y
        r"change\s+`([^`]+)`\s*->\s*`([^`]+)`",
        r"replace\s+`([^`]+)`\s*->\s*`([^`]+)`",
    ]

    for pattern in patterns:
        match = re.search(pattern, instructions, flags=re.IGNORECASE)
        if match:
            return match.group(1), match.group(2)

    return None


def parse_target_line(instructions: str) -> int | None:
    patterns = [
        r"\bline\s+(\d+)\b",
        r"\bon\s+line\s+(\d+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, instructions, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def get_first_function_name(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return node.name

    return None


def replace_function_by_name(
    original_content: str,
    replacement_snippet: str,
) -> str | None:
    function_name = get_first_function_name(replacement_snippet)

    if not function_name:
        return None

    try:
        tree = ast.parse(original_content)
    except SyntaxError:
        return None

    target_node = None

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name == function_name:
                target_node = node
                break

    if target_node is None:
        return None

    if target_node.end_lineno is None:
        return None

    original_lines = original_content.splitlines(keepends=True)

    start_index = target_node.lineno - 1
    end_index = target_node.end_lineno

    replacement_lines = replacement_snippet.strip().splitlines()
    replacement_text = "\n".join(replacement_lines) + "\n"

    new_lines = (
        original_lines[:start_index]
        + [replacement_text]
        + original_lines[end_index:]
    )

    return "".join(new_lines)


def replace_line_by_number(
    original_content: str,
    line_number: int,
    replacement_line: str,
) -> str | None:
    if line_number < 1:
        return None

    lines = original_content.splitlines(keepends=True)

    if line_number > len(lines):
        return None

    original_line = lines[line_number - 1]
    line_ending = "\n" if original_line.endswith("\n") else ""

    indent_match = re.match(r"^(\s*)", original_line)
    indent = indent_match.group(1) if indent_match else ""

    clean_replacement = replacement_line.strip()

    lines[line_number - 1] = f"{indent}{clean_replacement}{line_ending}"

    return "".join(lines)


def replace_exact_text(
    original_content: str,
    old_text: str,
    new_text: str,
) -> str | None:
    if old_text not in original_content:
        return None

    return original_content.replace(old_text, new_text, 1)


def build_modified_content(
    original_content: str,
    change: dict[str, Any],
) -> str:
    instructions = change.get("instructions") or ""
    replacement_snippet = change.get("replacement_snippet")
    old_text = change.get("old_text") or change.get("search_text")
    new_text = change.get("new_text") or change.get("replacement_text")
    target_line = change.get("target_line")

    # 1. Best case: explicit old/new text from a structured repair plan.
    if old_text and new_text:
        modified = replace_exact_text(
            original_content=original_content,
            old_text=str(old_text),
            new_text=str(new_text),
        )

        if modified is not None:
            return modified

    # 2. Parse natural-language instruction:
    #    "change `def hello()` to `def hello():`"
    exact_replace = parse_replace_instruction(instructions)

    if exact_replace:
        parsed_old_text, parsed_new_text = exact_replace

        modified = replace_exact_text(
            original_content=original_content,
            old_text=parsed_old_text,
            new_text=parsed_new_text,
        )

        if modified is not None:
            return modified

    # 3. Replace by explicit target_line if present.
    if target_line and replacement_snippet:
        modified = replace_line_by_number(
            original_content=original_content,
            line_number=int(target_line),
            replacement_line=str(replacement_snippet),
        )

        if modified is not None:
            return modified

    # 4. Parse line number from instruction:
    #    "On line 1, change ..."
    parsed_line = parse_target_line(instructions)

    if parsed_line and replacement_snippet:
        modified = replace_line_by_number(
            original_content=original_content,
            line_number=parsed_line,
            replacement_line=str(replacement_snippet),
        )

        if modified is not None:
            return modified

    # 5. Replace full function safely when the replacement snippet is complete Python.
    if replacement_snippet:
        function_replaced = replace_function_by_name(
            original_content=original_content,
            replacement_snippet=str(replacement_snippet),
        )

        if function_replaced is not None:
            return function_replaced

    raise ValueError(
        f"Could not safely build modification for file: {change.get('file_path')}"
    )


def build_unified_diff(
    file_path: str,
    old_content: str,
    new_content: str,
) -> str:
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )


def build_patches_from_repair_plan(
    project_root: Path,
    repair_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    patches: list[dict[str, Any]] = []

    changes = repair_plan.get("proposed_file_changes", [])

    for change in changes:
        change_type = change.get("change_type")
        file_path = change.get("file_path")

        if change_type not in SUPPORTED_CHANGE_TYPES:
            continue

        if not file_path:
            continue

        target_file = resolve_project_file(project_root, file_path)

        if change_type == "create":
            if target_file.exists():
                raise ValueError(
                    f"Cannot create file because it already exists: {file_path}"
                )

            new_content = change.get("replacement_snippet") or ""
            old_content = ""

        elif change_type in {"modify", "dependency"}:
            if not target_file.exists():
                raise FileNotFoundError(f"Target file does not exist: {file_path}")

            old_content = target_file.read_text(encoding="utf-8", errors="replace")

            if change_type == "dependency" and change.get("replacement_snippet"):
                new_content = str(change["replacement_snippet"]).strip() + "\n"
            else:
                new_content = build_modified_content(old_content, change)

        else:
            continue

        diff = build_unified_diff(
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
        )

        patches.append(
            {
                "file_path": file_path,
                "change_type": change_type,
                "diff": diff,
                "new_content": new_content,
                "can_apply": bool(diff.strip()),
            }
        )

    return patches


def apply_patches_to_project(
    project_root: Path,
    patches: list[dict[str, Any]],
) -> list[str]:
    applied_files: list[str] = []

    for patch in patches:
        if not patch.get("can_apply"):
            continue

        file_path = patch["file_path"]
        target_file = resolve_project_file(project_root, file_path)

        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(
            patch["new_content"],
            encoding="utf-8",
        )

        applied_files.append(file_path)

    return applied_files