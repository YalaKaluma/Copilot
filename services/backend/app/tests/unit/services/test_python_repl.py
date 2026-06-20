from __future__ import annotations

import json
from pathlib import Path

from services.python_repl import ExecResult, PythonREPL, get_session_data_dir


def test_get_session_data_dir_is_scoped_and_created(tmp_path, monkeypatch):
    monkeypatch.setattr("services.python_repl.SANDBOX_SHARED_DIR", tmp_path)

    data_dir = get_session_data_dir("abc/../123")

    assert data_dir.as_posix() == (tmp_path / "data" / "abc-123").as_posix()
    assert data_dir.exists()


def test_run_submits_job_and_reads_result(tmp_path, monkeypatch):
    monkeypatch.setattr("services.python_repl.SANDBOX_SHARED_DIR", tmp_path)

    repl = PythonREPL("session-1")
    jobs_dir = tmp_path / "jobs"
    captured_request: dict = {}

    polls = {"count": 0}

    def fake_sleep(_: float) -> None:
        polls["count"] += 1
        if polls["count"] == 1:
            job_dir = next(jobs_dir.iterdir())
            request = json.loads((job_dir / "request.json").read_text(encoding="utf-8"))
            captured_request["request"] = request
            payload = {
                "stdout": request["code"] + "\n",
                "stderr": "",
                "ok": True,
            }
            (job_dir / "result.json").write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

    monkeypatch.setattr("services.python_repl.time.sleep", fake_sleep)

    result = repl.run("print('ok')", timeout=1.0)

    assert result == ExecResult(stdout="print('ok')\n", stderr="", ok=True)
    assert captured_request["request"]["session_id"] == "session-1"


def test_run_times_out_when_worker_never_replies(tmp_path, monkeypatch):
    monkeypatch.setattr("services.python_repl.SANDBOX_SHARED_DIR", tmp_path)
    repl = PythonREPL("session-1")

    clock = {"now": 0.0}

    def fake_monotonic() -> float:
        clock["now"] += 1.0
        return clock["now"]

    monkeypatch.setattr("services.python_repl.time.monotonic", fake_monotonic)
    monkeypatch.setattr("services.python_repl.time.sleep", lambda _: None)
    # Prevent rmtree so we can assert the cancel file was written
    monkeypatch.setattr("services.python_repl.shutil.rmtree", lambda *_, **__: None)

    result = repl.run("1 + 1", timeout=1.0)

    assert result.ok is False
    assert "timed out" in result.stderr
    job_dir = next((tmp_path / "jobs").iterdir())
    assert (job_dir / "cancelled").exists()


def test_run_reports_shared_dir_error(monkeypatch, tmp_path):
    repl = PythonREPL("session-1")

    def fail(*_args, **_kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "mkdir", fail)
    monkeypatch.setattr("services.python_repl.SANDBOX_SHARED_DIR", tmp_path)

    result = repl.run("1 + 1")

    assert result.ok is False
    assert "shared directory" in result.stderr
