from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent.graph import build_repair_graph
from app.patching.diff_builder import (
    apply_patches_to_project,
    build_patches_from_repair_plan,
)
from app.projects.issue_store import (
    get_project_issue,
    get_project_issues,
    get_project_patches,
    get_repair_plan,
    save_project_issues,
    save_project_patches,
    save_repair_plan,
)
from app.projects.registry import get_project, list_projects
from app.scanner.project_issue_scanner import ScanIssue, ToolRun, scan_project
from app.schemas.api import (
    ApplyPatchResponse,
    BuildDiffResponse,
    IssuesResponse,
    PatchDiffItem,
    ProjectItem,
    ProposeFixResponse,
    RepairRequest,
    RepairResponse,
    ScanIssueItem,
    ScanProjectResponse,
    ToolRunItem,
)

app = FastAPI(
    title="AI Coding Assistant",
    version="0.1.0",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def to_tool_run_item(tool_run: ToolRun) -> ToolRunItem:
    return ToolRunItem(
        tool=tool_run.tool,
        command=tool_run.command,
        status=tool_run.status,
        exit_code=tool_run.exit_code,
        output=tool_run.output,
        summary=getattr(tool_run, "summary", ""),
        suggested_action=getattr(tool_run, "suggested_action", None),
        raw_output=getattr(tool_run, "raw_output", tool_run.output),
    )


def to_scan_issue_item(issue: ScanIssue) -> ScanIssueItem:
    return ScanIssueItem(
        id=issue.id,
        tool=issue.tool,
        title=issue.title,
        severity=issue.severity,
        details=issue.details,
        command=issue.command,
        summary=getattr(issue, "summary", ""),
        location=getattr(issue, "location", None),
        suggested_action=getattr(issue, "suggested_action", None),
        raw_details=getattr(issue, "raw_details", issue.details),
    )


def build_issue_problem(project_id: str, project_name: str, project_path: Path, issue: ScanIssue) -> str:
    issue_summary = getattr(issue, "summary", "") or issue.title
    issue_location = getattr(issue, "location", None)
    issue_action = getattr(issue, "suggested_action", None)
    raw_details = getattr(issue, "raw_details", issue.details)

    return f"""
Automated project scan detected an issue.

Project:
- id: {project_id}
- name: {project_name}
- path: {project_path}

Issue:
- id: {issue.id}
- tool: {issue.tool}
- title: {issue.title}
- severity: {issue.severity}
- command: {issue.command}
- summary: {issue_summary}
- location: {issue_location or "not detected"}
- suggested_action: {issue_action or "not provided"}

Details:
{raw_details}

Task:
Analyze this detected issue and propose a safe repair plan.
Do not apply changes.
Propose file changes only.
"""


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/repair", response_model=RepairResponse)
def repair_code(request: RepairRequest) -> RepairResponse:
    try:
        graph = build_repair_graph()

        result = graph.invoke(
            {
                "problem": request.problem,
            }
        )

        return RepairResponse(
            context_report=result.get("context_report", ""),
            repair_plan=result["repair_plan"],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@app.get("/projects", response_model=list[ProjectItem])
def get_projects() -> list[ProjectItem]:
    return [
        ProjectItem(
            id=project.id,
            name=project.name,
            description=project.description,
        )
        for project in list_projects()
    ]


@app.post("/projects/{project_id}/scan", response_model=ScanProjectResponse)
def scan_selected_project(project_id: str) -> ScanProjectResponse:
    try:
        project = get_project(project_id)
        result = scan_project(project.id, project.path)

        save_project_issues(project.id, result.issues)

        return ScanProjectResponse(
            project_id=result.project_id,
            tool_runs=[
                to_tool_run_item(tool_run)
                for tool_run in result.tool_runs
            ],
            issues=[
                to_scan_issue_item(issue)
                for issue in result.issues
            ],
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/projects/{project_id}/issues", response_model=IssuesResponse)
def list_project_issues(project_id: str) -> IssuesResponse:
    try:
        project = get_project(project_id)
        issues = get_project_issues(project.id)

        return IssuesResponse(
            project_id=project.id,
            issues=[
                to_scan_issue_item(issue)
                for issue in issues
            ],
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/issues/{issue_id}/propose-fix",
    response_model=ProposeFixResponse,
)
def propose_fix_for_issue(project_id: str, issue_id: str) -> ProposeFixResponse:
    try:
        project = get_project(project_id)
        issue = get_project_issue(project.id, issue_id)

        problem = build_issue_problem(
            project_id=project.id,
            project_name=project.name,
            project_path=project.path,
            issue=issue,
        )

        graph = build_repair_graph()

        result = graph.invoke(
            {
                "problem": problem,
                "project_id": project.id,
                "project_path": str(project.path),
            }
        )

        save_repair_plan(
            project_id=project.id,
            issue_id=issue.id,
            repair_plan=result["repair_plan"],
        )

        return ProposeFixResponse(
            project_id=project.id,
            issue_id=issue.id,
            issue=to_scan_issue_item(issue),
            context_report=result.get("context_report", ""),
            repair_plan=result["repair_plan"],
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/issues/{issue_id}/build-diff",
    response_model=BuildDiffResponse,
)
def build_diff_for_issue(project_id: str, issue_id: str) -> BuildDiffResponse:
    try:
        project = get_project(project_id)
        repair_plan = get_repair_plan(project.id, issue_id)

        patches = build_patches_from_repair_plan(
            project_root=project.path,
            repair_plan=repair_plan,
        )

        save_project_patches(
            project_id=project.id,
            issue_id=issue_id,
            patches=patches,
        )

        return BuildDiffResponse(
            project_id=project.id,
            issue_id=issue_id,
            patches=[
                PatchDiffItem(
                    file_path=patch["file_path"],
                    change_type=patch["change_type"],
                    diff=patch["diff"],
                    can_apply=patch["can_apply"],
                )
                for patch in patches
            ],
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/issues/{issue_id}/apply",
    response_model=ApplyPatchResponse,
)
def apply_fix_for_issue(project_id: str, issue_id: str) -> ApplyPatchResponse:
    try:
        project = get_project(project_id)
        patches = get_project_patches(project.id, issue_id)

        applied_files = apply_patches_to_project(
            project_root=project.path,
            patches=patches,
        )

        result = scan_project(project.id, project.path)
        save_project_issues(project.id, result.issues)

        return ApplyPatchResponse(
            project_id=project.id,
            issue_id=issue_id,
            applied_files=applied_files,
            tool_runs=[
                to_tool_run_item(tool_run)
                for tool_run in result.tool_runs
            ],
            issues=[
                to_scan_issue_item(issue)
                for issue in result.issues
            ],
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/sonar/demo/issues")
def list_demo_sonar_issues(limit: int = 50) -> dict:
    try:
        issues = fetch_demo_sonar_issues(limit=limit)

        return {
            "project_key": "ai-coding-demo-projects",
            "total": len(issues),
            "issues": issues,
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/sonar/demo/issues/{issue_key}/prompt")
def get_demo_sonar_issue_prompt(issue_key: str) -> dict:
    try:
        issue = get_demo_sonar_issue(issue_key)

        prompt_payload = build_sonar_issue_prompt(
            issue=issue,
            project_root=Path.cwd(),
        )

        return {
            "issue": issue,
            "prompt": prompt_payload["prompt"],
        }

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc