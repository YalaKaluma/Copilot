"""Prompt optimizer: page and API for editing prompts and saving new Skai versions."""

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from config.versioning import (
    TEMP_VERSION_ID,
    create_new_version_based_on_modified_prompts,
    get_copilot_version,
    list_base_version_ids,
    save_prompt_to_version,
)
from core.exceptions import AppConfigError
from core.config import get_settings
from evaluation.run_evaluations import run_evals
from schemas.prompt_optimizer import (
    SavePromptRequest,
    SaveNewVersionRequest,
    RunExperimentRequest,
)

router = APIRouter(prefix="/prompt-optimizer", tags=["Prompt optimizer"])

_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
_OPTIMIZER_HTML = _STATIC_DIR / "prompt_optimizer.html"


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------


def _require_dev() -> None:
    """Raise 404 if not in development (prompt optimizer is dev-only)."""
    if get_settings().env != "development":
        raise HTTPException(status_code=404, detail="Not found")


RequireDev = Annotated[None, Depends(lambda: _require_dev())]


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.get("", include_in_schema=False)
async def get_optimizer_page(_: RequireDev):
    """Serve the prompt optimizer HTML page."""
    if not _OPTIMIZER_HTML.is_file():
        raise HTTPException(status_code=404, detail="Prompt optimizer page not found")
    return FileResponse(_OPTIMIZER_HTML, media_type="text/html")


@router.get("/versions")
async def list_versions(_: RequireDev) -> dict:
    """List base copilot version ids (config/versions/*.yaml, excludes temp)."""
    return {"versionIds": list_base_version_ids()}


@router.get("/versions/{version_id}")
async def get_version_config(version_id: str, _: RequireDev) -> dict:
    """Get version config and prompt keys for the selected version."""
    try:
        resolved = get_copilot_version(version_id, no_cache=False)
    except AppConfigError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    config = resolved.config
    return {
        "version": config.version,
        "tools": getattr(config, "tools", None),
        "model": config.model.model_dump() if config.model else None,
        "executionAgents": [a.model_dump() for a in config.execution_agents],
        "promptKeys": resolved.prompt_keys(),
    }


@router.get("/versions/{version_id}/prompts/{key}", response_class=PlainTextResponse)
async def get_prompt_content(version_id: str, key: str, _: RequireDev) -> str:
    """Get raw prompt content for editing (always from local files)."""
    try:
        resolved = get_copilot_version(version_id, no_cache=False)
        return resolved.get_prompt_raw(key)
    except AppConfigError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/versions/{version_id}/prompts/{key}/save")
async def save_prompt(
    version_id: str, key: str, body: SavePromptRequest, _: RequireDev
) -> dict:
    """Save a single prompt under the given prompt version (writes name/{prompt_version}.j2 only)."""
    if version_id == TEMP_VERSION_ID:
        raise HTTPException(
            status_code=400,
            detail="Save prompt from a base Skai version (e.g. v1), not from temp.",
        )
    pv = (body.prompt_version or "").strip()
    if not pv:
        raise HTTPException(status_code=400, detail="prompt_version is required")
    try:
        save_prompt_to_version(version_id, key, body.content, pv)
    except AppConfigError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"saved": key, "prompt_version": pv}


@router.post("/versions/{version_id}/save-new-version")
async def save_new_version(
    version_id: str, body: SaveNewVersionRequest, _: RequireDev
) -> dict:
    """Create a new Skai version YAML; reuses base prompt refs for unsaved prompts.

    Uses prompt_version to decide which prompts use the new ref (where
    name/{prompt_version}.j2 exists); others keep the base version's refs.
    """
    if version_id == TEMP_VERSION_ID:
        raise HTTPException(
            status_code=400,
            detail="Use a base Skai version (e.g. v1) as the base for the new version.",
        )
    new_id = body.new_version_id.strip()
    pv = body.prompt_version.strip()
    if not new_id or not pv:
        raise HTTPException(
            status_code=400,
            detail="new_version_id and prompt_version are required",
        )
    try:
        create_new_version_based_on_modified_prompts(version_id, new_id)
    except AppConfigError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"versionId": new_id}


@router.post("/experiment")
async def run_experiment(
    body: RunExperimentRequest,
    _: RequireDev,
) -> dict:
    """Run an evaluation experiment for the given system_version (copilot version id).

    Runs evals in a thread so the request blocks until complete; use a long client
    timeout for large datasets. On success returns run info; on failure returns 4xx/5xx.
    """
    try:
        get_copilot_version(body.system_version)
    except (AppConfigError, ValueError) as e:
        raise HTTPException(
            status_code=404 if isinstance(e, AppConfigError) else 400,
            detail=e.message if isinstance(e, AppConfigError) else str(e),
        ) from e

    exit_code = await asyncio.to_thread(
        run_evals,
        dataset_name=body.dataset_name,
        mode=body.mode,
        run_name=body.run_name or "",
        system_version=body.system_version,
        limit=body.limit,
    )
    if exit_code != 0:
        raise HTTPException(
            status_code=502,
            detail="Evaluation run failed (check backend logs for details).",
        )
    return {
        "runName": body.run_name or f"copilot-eval-{body.system_version}",
        "systemVersion": body.system_version,
        "datasetName": body.dataset_name,
        "mode": body.mode,
    }
