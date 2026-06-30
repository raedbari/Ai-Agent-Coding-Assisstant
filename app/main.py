from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.api import router as agent_router
from app.projects.registry import get_project, list_projects
from app.security.sonar_client import fetch_demo_sonar_issues
from app.security.sonar_github_apply import push_sonar_project_diff_to_github
from app.security.sonar_project_llm_fix import propose_project_sonar_fix_with_llm


app = FastAPI(
    title="AI Coding Assistant",
    version="0.1.0",
)
# Imports #
app.include_router(agent_router)

@app.middleware("http")
async def disable_cache_for_frontend(request: Request, call_next):
    response = await call_next(request)

    path = request.url.path

    if path == "/" or path == "/index.html" or path.startswith("/static/"):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Surrogate-Control"] = "no-store"

    return response


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ApplySonarProjectFixRequest(BaseModel):
    model_output: str


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/projects")
def get_projects() -> list[dict[str, str]]:
    return [
        {
            "id": project.id,
            "name": project.name,
            "description": project.description,
        }
        for project in list_projects()
    ]


def filter_sonar_issues_by_project(
    issues: list[dict[str, Any]],
    project_id: str,
) -> list[dict[str, Any]]:
    project = get_project(project_id)

    project_root = Path.cwd().resolve()
    project_path = project.path.resolve()

    try:
        file_prefix = project_path.relative_to(project_root).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"Project path is outside application root: {project.path}"
        ) from exc

    file_prefix = file_prefix.rstrip("/") + "/"

    return [
        issue
        for issue in issues
        if issue.get("file_path", "").startswith(file_prefix)
    ]


@app.get("/sonar/demo/issues")
def list_demo_sonar_issues(
    limit: int = 50,
    project_id: str | None = None,
) -> dict[str, Any]:
    try:
        issues = fetch_demo_sonar_issues(limit=limit)

        if project_id:
            issues = filter_sonar_issues_by_project(
                issues=issues,
                project_id=project_id,
            )

        return {
            "project_key": "ai-coding-demo-projects",
            "project_id": project_id,
            "total": len(issues),
            "issues": issues,
        }

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/sonar/demo/projects/{project_id}/propose-fix")
def propose_demo_sonar_project_fix(project_id: str) -> dict[str, Any]:
    try:
        all_issues = fetch_demo_sonar_issues(limit=100)

        project_issues = filter_sonar_issues_by_project(
            issues=all_issues,
            project_id=project_id,
        )

        if not project_issues:
            return {
                "project_id": project_id,
                "total": 0,
                "issues": [],
                "prompt": "",
                "model_output": "No SonarQube issues found for this project.",
            }

        result = propose_project_sonar_fix_with_llm(
            issues=project_issues,
            project_root=Path.cwd(),
        )

        return {
            "project_id": project_id,
            "total": len(project_issues),
            "issues": project_issues,
            "prompt": result["prompt"],
            "model_output": result["model_output"],
        }

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/sonar/demo/projects/{project_id}/apply-fix")
def apply_demo_sonar_project_fix(
    project_id: str,
    request: ApplySonarProjectFixRequest,
) -> dict[str, Any]:
    try:
        project = get_project(project_id)

        result = push_sonar_project_diff_to_github(
            diff_text=request.model_output,
            project_id=project.id,
            project_path=project.path,
            project_root=Path.cwd(),
        )

        return {
            "project_id": project_id,
            **result,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc