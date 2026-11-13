import sys
import tempfile
import uuid
import pytest
from pathlib import Path
from src.infrastructure.execution.process_manager import (
    ProjectProcessManager,
    find_available_port,
)


def test_find_available_port():
    port = find_available_port(5200, reserved_ports={5200})
    assert port > 5200


def test_resolve_launch_details_csharp(tmp_path):
    mgr = ProjectProcessManager(base_workspace_dir=str(tmp_path))
    proj_id = uuid.uuid4()
    channel_dir = tmp_path / str(proj_id) / "channel-app"
    channel_dir.mkdir(parents=True)
    (channel_dir / "channel-app.csproj").write_text("<Project />", encoding="utf-8")

    cmd, cwd, port, url = mgr._resolve_launch_details(proj_id, "DOTNET_CSHARP")
    assert "dotnet" in cmd[0]
    assert "run" in cmd[1]
    assert str(cwd) == str(channel_dir)
    assert f":{port}/swagger" in url


def test_resolve_launch_details_fastapi(tmp_path):
    mgr = ProjectProcessManager(base_workspace_dir=str(tmp_path))
    proj_id = uuid.uuid4()
    channel_dir = tmp_path / str(proj_id) / "channel-app"
    channel_dir.mkdir(parents=True)
    (channel_dir / "src").mkdir()
    (channel_dir / "src" / "main.py").write_text("# api", encoding="utf-8")

    cmd, cwd, port, url = mgr._resolve_launch_details(proj_id, "PYTHON_FASTAPI")
    assert "uvicorn" in " ".join(cmd)
    assert f":{port}/docs" in url


def test_resolve_launch_details_frontend(tmp_path):
    mgr = ProjectProcessManager(base_workspace_dir=str(tmp_path))
    proj_id = uuid.uuid4()
    frontend_dir = tmp_path / str(proj_id) / "frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "package.json").write_text("{}", encoding="utf-8")

    cmd, cwd, port, url = mgr._resolve_launch_details(proj_id, "TYPESCRIPT_NEXTJS", subsystem="frontend")
    assert "npm" in cmd[0]
    assert "run" in cmd[1]
    assert str(cwd) == str(frontend_dir)
    assert f":{port}" in url


def test_start_and_stop_mock_process(tmp_path):
    mgr = ProjectProcessManager(base_workspace_dir=str(tmp_path))
    proj_id = uuid.uuid4()
    channel_dir = tmp_path / str(proj_id) / "channel-app"
    channel_dir.mkdir(parents=True)

    # Monkeypatch launch details to run a safe python echo process
    def dummy_launch(*args, **kwargs):
        cmd = [sys.executable, "-c", "import time, sys; sys.stdout.write('Service started\\n'); sys.stdout.flush(); time.sleep(5)"]
        return cmd, channel_dir, 5555, "http://localhost:5555"

    mgr._resolve_launch_details = dummy_launch

    res = mgr.start_project(proj_id, "DOTNET_CSHARP")
    assert res["status"] == "RUNNING"
    assert res["info"]["port"] == 5555
    assert res["info"]["pid"] > 0

    status = mgr.get_status(proj_id)
    assert status["status"] == "RUNNING"

    # Stop process
    stop_res = mgr.stop_project(proj_id)
    assert stop_res["status"] == "STOPPED"

    status_after = mgr.get_status(proj_id)
    assert status_after["status"] == "STOPPED"
