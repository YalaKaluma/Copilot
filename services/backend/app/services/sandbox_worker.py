import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

SANDBOX_SHARED_DIR = Path(os.getenv("PYTHON_SANDBOX_SHARED_DIR", "/sandbox")).resolve()
DATA_DIR = SANDBOX_SHARED_DIR / "data"
JOBS_DIR = SANDBOX_SHARED_DIR / "jobs"
_SHARED_DIR_MODE = 0o777
REQUEST_FILE_NAME = "request.json"
PROCESSING_FILE_NAME = "processing.json"
RESULT_FILE_NAME = "result.json"
CANCEL_FILE_NAME = "cancelled"
POLL_INTERVAL_SECONDS = 0.1
MAX_TIMEOUT_SECONDS = 30.0


class RequestBody(TypedDict):
    session_id: str
    timeout: float
    code: str


class ResultBody(TypedDict):
    stdout: str
    stderr: str
    ok: bool


def _bootstrap_source() -> str:
    return """
import ast
import sys
from pathlib import Path

code_path = Path(sys.argv[1])
source = code_path.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(code_path), mode="exec")
namespace = {"__name__": "__main__", "__file__": str(code_path)}

if tree.body and isinstance(tree.body[-1], ast.Expr):
    prefix = ast.Module(body=tree.body[:-1], type_ignores=[])
    tail = ast.Expression(tree.body[-1].value)
    ast.fix_missing_locations(prefix)
    ast.fix_missing_locations(tail)

    if prefix.body:
        exec(compile(prefix, str(code_path), "exec"), namespace, namespace)

    value = eval(compile(tail, str(code_path), "eval"), namespace, namespace)
    if value is not None:
        print(repr(value))
else:
    exec(compile(tree, str(code_path), "exec"), namespace, namespace)
"""


def _write_json(path: Path, payload: ResultBody) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload), encoding="utf-8")
    temp_path.replace(path)


def _child_limits() -> None:
    memory_limit_bytes = 512 * 1024 * 1024
    file_limit_bytes = 10 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (35, 35))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit_bytes, file_limit_bytes))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def _minimal_env() -> dict[str, str]:
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/tmp",
        "PYTHONNOUSERSITE": "1",
        # Avoid OpenBLAS spawning many threads; sandbox has low RLIMIT_NPROC (64).
        "OPENBLAS_NUM_THREADS": "1",
    }


def _execute_job(job_dir: Path, request: RequestBody) -> ResultBody:
    session_id = request["session_id"]
    timeout = min(request["timeout"], MAX_TIMEOUT_SECONDS)
    code = request["code"]

    session_data_dir = DATA_DIR / session_id
    session_data_dir.mkdir(parents=True, exist_ok=True, mode=_SHARED_DIR_MODE)

    run_dir = job_dir / "run"
    run_dir.mkdir(exist_ok=True)

    code_path = run_dir / "user_code.py"
    bootstrap_path = run_dir / "bootstrap.py"
    code_path.write_text(code, encoding="utf-8")
    bootstrap_path.write_text(_bootstrap_source(), encoding="utf-8")

    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(bootstrap_path), str(code_path)],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_minimal_env(),
            preexec_fn=_child_limits,
        )
    except subprocess.TimeoutExpired:
        return ResultBody(
            stdout="",
            stderr=f"Execution timed out after {timeout} seconds.\n",
            ok=False,
        )
    except BaseException as exc:
        return ResultBody(
            stdout="",
            stderr=f"Sandbox execution failed: {exc}\n",
            ok=False,
        )

    return ResultBody(
        stdout=completed.stdout,
        stderr=completed.stderr,
        ok=completed.returncode == 0,
    )


def _claim_request(request_path: Path) -> Path | None:
    processing_path = request_path.with_name(PROCESSING_FILE_NAME)
    try:
        request_path.replace(processing_path)
    except FileNotFoundError:
        return None
    return processing_path


def _process_request(processing_path: Path) -> None:
    job_dir = processing_path.parent
    result_path = job_dir / RESULT_FILE_NAME

    request = json.loads(processing_path.read_text(encoding="utf-8"))
    if (job_dir / CANCEL_FILE_NAME).exists():
        result = ResultBody(
            stdout="",
            stderr="Execution cancelled.\n",
            ok=False,
        )
    else:
        result = _execute_job(job_dir, request)

    _write_json(result_path, result)
    processing_path.unlink(missing_ok=True)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=_SHARED_DIR_MODE)
    JOBS_DIR.mkdir(parents=True, exist_ok=True, mode=_SHARED_DIR_MODE)

    while True:
        processed = False
        for request_path in sorted(JOBS_DIR.glob(f"*/{REQUEST_FILE_NAME}")):
            claimed_path = _claim_request(request_path)
            if claimed_path is None:
                continue
            processed = True
            _process_request(claimed_path)

        if not processed:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
