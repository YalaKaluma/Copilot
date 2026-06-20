import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

SANDBOX_SHARED_DIR = Path(os.getenv("PYTHON_SANDBOX_SHARED_DIR", "/sandbox")).resolve()
SANDBOX_DATA_DIR_NAME = "data"
SANDBOX_JOBS_DIR_NAME = "jobs"
_SHARED_DIR_MODE = 0o777
_REQUEST_FILE_NAME = "request.json"
_RESULT_FILE_NAME = "result.json"
_PROCESSING_FILE_NAME = "processing.json"
_CANCEL_FILE_NAME = "cancelled"
_SESSION_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_POLL_INTERVAL_SECONDS = 0.1


@dataclass(slots=True)
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    ok: bool = True


def _safe_session_id(session_id: str) -> str:
    cleaned = _SESSION_ID_RE.sub("-", session_id)
    # Collapse ".." and surrounding hyphens so e.g. "abc/../123" -> "abc-123"
    cleaned = re.sub(r"-*\.\.+-*", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip(".-")
    if not cleaned:
        raise ValueError("Session ID cannot be empty")
    return cleaned


def _ensure_shared_dirs() -> tuple[Path, Path]:
    jobs_dir = SANDBOX_SHARED_DIR / SANDBOX_JOBS_DIR_NAME
    data_dir = SANDBOX_SHARED_DIR / SANDBOX_DATA_DIR_NAME
    jobs_dir.mkdir(parents=True, exist_ok=True, mode=_SHARED_DIR_MODE)
    data_dir.mkdir(parents=True, exist_ok=True, mode=_SHARED_DIR_MODE)
    return jobs_dir, data_dir


def get_session_data_dir(session_id: str) -> Path:
    _, data_root = _ensure_shared_dirs()
    session_dir = data_root / _safe_session_id(session_id)
    session_dir.mkdir(parents=True, exist_ok=True, mode=_SHARED_DIR_MODE)
    return session_dir


def _write_json(path: Path, payload: dict[str, object]) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload), encoding="utf-8")
    temp_path.replace(path)


def _read_result(path: Path) -> ExecResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExecResult(
        stdout=str(payload.get("stdout", "")),
        stderr=str(payload.get("stderr", "")),
        ok=bool(payload.get("ok", False)),
    )


class PythonREPL:
    def __init__(self, session_id: str) -> None:
        self._session_id = session_id

    def run(self, code: str, timeout: float = 30.0) -> ExecResult:
        try:
            jobs_dir, _ = _ensure_shared_dirs()
        except OSError as exc:
            return ExecResult(
                stderr=(
                    "Local code execution sandbox is unavailable because "
                    f"the shared directory {SANDBOX_SHARED_DIR} could not be prepared: {exc}\n"
                ),
                ok=False,
            )

        job_id = uuid.uuid4().hex
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=False)

        request_path = job_dir / _REQUEST_FILE_NAME
        result_path = job_dir / _RESULT_FILE_NAME
        cancel_path = job_dir / _CANCEL_FILE_NAME

        _write_json(
            request_path,
            {
                "job_id": job_id,
                "session_id": _safe_session_id(self._session_id),
                "timeout": timeout,
                "code": code,
            },
        )

        deadline = time.monotonic() + timeout + 2.0
        while time.monotonic() < deadline:
            if result_path.exists():
                exec_result = _read_result(result_path)
                shutil.rmtree(job_dir, ignore_errors=True)
                return exec_result
            time.sleep(_POLL_INTERVAL_SECONDS)

        cancel_path.write_text("", encoding="utf-8")
        processing_path = job_dir / _PROCESSING_FILE_NAME
        status_hint = (
            " The sandbox worker may be unavailable."
            if request_path.exists() and not processing_path.exists()
            else ""
        )
        shutil.rmtree(job_dir, ignore_errors=True)
        return ExecResult(
            stderr=f"Execution timed out after {timeout} seconds.{status_hint}\n",
            ok=False,
        )

    def cleanup(self) -> None:
        data_dir = get_session_data_dir(self._session_id)

        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)
