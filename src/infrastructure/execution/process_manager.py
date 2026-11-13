import collections
import datetime
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ProcessInfo:
    def __init__(
        self,
        project_id: str,
        subsystem: str,
        pid: int,
        port: int,
        url: str,
        command: list[str],
        cwd: str,
        process: subprocess.Popen,
    ) -> None:
        self.project_id = project_id
        self.subsystem = subsystem
        self.pid = pid
        self.port = port
        self.url = url
        self.command = command
        self.cwd = cwd
        self.process = process
        self.status = "RUNNING"
        self.started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.log_lines: collections.deque[str] = collections.deque(maxlen=1000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "subsystem": self.subsystem,
            "pid": self.pid,
            "port": self.port,
            "url": self.url,
            "status": self.status,
            "started_at": self.started_at,
            "log_count": len(self.log_lines),
        }


def find_available_port(start_port: int, reserved_ports: set[int] | None = None) -> int:
    reserved = reserved_ports or {8080, 8081, 11434}
    port = start_port
    while port < 65535:
        if port not in reserved:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                res = s.connect_ex(("127.0.0.1", port))
                if res != 0:
                    # Port is free
                    return port
        port += 1
    raise RuntimeError(f"No available port found starting from {start_port}")


class ProjectProcessManager:
    _instance = None

    def __init__(self, base_workspace_dir: str = "./workspace") -> None:
        self.base_workspace_dir = Path(base_workspace_dir).resolve()
        self._processes: dict[str, ProcessInfo] = {}  # key: f"{project_id}_{subsystem}"
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls, base_workspace_dir: str = "./workspace") -> "ProjectProcessManager":
        if cls._instance is None:
            cls._instance = ProjectProcessManager(base_workspace_dir)
        return cls._instance

    def _resolve_launch_details(
        self,
        project_id: uuid.UUID | str,
        target_framework: str,
        subsystem: str = "channel-app",
    ) -> tuple[list[str], Path, int, str]:
        p_id = str(project_id)
        proj_dir = self.base_workspace_dir / p_id
        framework_lower = (target_framework or "").lower()

        # Check frontend subsystem
        if subsystem == "frontend" or (proj_dir / "frontend").exists() and subsystem != "channel-app":
            cwd = proj_dir / "frontend"
            port = find_available_port(3000)
            npm_bin = "npm.cmd" if sys.platform == "win32" else "npm"
            cmd = [npm_bin, "run", "dev", "--", "-p", str(port)]
            url = f"http://localhost:{port}"
            return cmd, cwd, port, url

        # Channel app (backend)
        cwd = proj_dir / "channel-app"
        if any(k in framework_lower for k in ("cs", "csharp", "dotnet", "net")):
            port = find_available_port(5001)
            csprojs = list(cwd.glob("*.csproj"))
            if csprojs:
                target = str(csprojs[0])
            elif (cwd / "channel-app.sln").exists():
                target = str(cwd / "channel-app.sln")
            else:
                target = "."
            cmd = ["dotnet", "run", "--project", target, "--urls", f"http://localhost:{port}"]
            url = f"http://localhost:{port}/swagger"
            return cmd, cwd, port, url

        if any(k in framework_lower for k in ("py", "python", "fastapi", "flask", "django")):
            port = find_available_port(8000)
            app_module = "src.main:app" if (cwd / "src" / "main.py").exists() else "main:app"
            cmd = [sys.executable, "-m", "uvicorn", app_module, "--port", str(port), "--host", "127.0.0.1"]
            url = f"http://localhost:{port}/docs"
            return cmd, cwd, port, url

        # Generic Node/JS
        port = find_available_port(3000)
        npm_bin = "npm.cmd" if sys.platform == "win32" else "npm"
        cmd = [npm_bin, "run", "dev", "--", "-p", str(port)]
        url = f"http://localhost:{port}"
        return cmd, cwd, port, url

    def start_project(
        self,
        project_id: uuid.UUID | str,
        target_framework: str,
        subsystem: str = "channel-app",
    ) -> dict[str, Any]:
        p_id = str(project_id)
        key = f"{p_id}_{subsystem}"

        with self._lock:
            # Check if already running
            existing = self._processes.get(key)
            if existing and existing.status == "RUNNING":
                if existing.process.poll() is None:
                    return {
                        "status": "ALREADY_RUNNING",
                        "message": f"Project {subsystem} is already active.",
                        "info": existing.to_dict(),
                    }
                else:
                    existing.status = "STOPPED"

            cmd, cwd, port, url = self._resolve_launch_details(project_id, target_framework, subsystem)

            if not cwd.exists():
                raise FileNotFoundError(f"Project directory {cwd} does not exist.")

            env = {
                **os.environ,
                "PORT": str(port),
                "ASPNETCORE_URLS": f"http://localhost:{port}",
                "ASPNETCORE_ENVIRONMENT": "Development",
            }

            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
            except Exception as e:
                logger.error(f"Failed to spawn project process: {e}")
                raise RuntimeError(f"Could not launch {cmd}: {e}")

            info = ProcessInfo(
                project_id=p_id,
                subsystem=subsystem,
                pid=proc.pid,
                port=port,
                url=url,
                command=cmd,
                cwd=str(cwd),
                process=proc,
            )
            self._processes[key] = info

            # Background thread to capture stdout/stderr safely
            def _log_reader(process: subprocess.Popen, log_buffer: collections.deque):
                try:
                    for line in iter(process.stdout.readline, ""):
                        if line:
                            log_buffer.append(line.rstrip())
                        else:
                            break
                except Exception:
                    pass
                finally:
                    if process.stdout:
                        process.stdout.close()
                    info.status = "STOPPED"

            t = threading.Thread(target=_log_reader, args=(proc, info.log_lines), daemon=True)
            t.start()

            # Poll briefly for socket readiness while verifying the process didn't crash on spawn
            start_wait = time.time()
            while time.time() - start_wait < 2.0:
                if proc.poll() is not None:
                    err_logs = list(info.log_lines)
                    err_msg = "\n".join(err_logs[-10:]) if err_logs else f"Exit code {proc.returncode}"
                    info.status = "STOPPED"
                    raise RuntimeError(f"Service exited prematurely:\n{err_msg}")
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.2)
                        if s.connect_ex(("127.0.0.1", port)) == 0:
                            break
                except Exception:
                    pass
                time.sleep(0.2)

            logger.info(f"Project {p_id} ({subsystem}) ready on port {port} (PID: {proc.pid})")
            return {
                "status": "RUNNING",
                "message": f"Project {subsystem} launched successfully.",
                "info": info.to_dict(),
            }

    def stop_project(
        self,
        project_id: uuid.UUID | str,
        subsystem: str | None = None,
    ) -> dict[str, Any]:
        p_id = str(project_id)
        stopped_keys: list[str] = []

        with self._lock:
            target_keys = [k for k in self._processes if k.startswith(f"{p_id}_")]
            if subsystem:
                target_keys = [f"{p_id}_{subsystem}"]

            for k in target_keys:
                info = self._processes.get(k)
                if not info:
                    continue

                proc = info.process
                if proc.poll() is None:
                    try:
                        if sys.platform == "win32":
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                capture_output=True,
                                timeout=10,
                            )
                        else:
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                    except Exception as e:
                        logger.warning(f"Error terminating process {proc.pid}: {e}")

                info.status = "STOPPED"
                stopped_keys.append(k)

        return {
            "status": "STOPPED",
            "message": f"Stopped {len(stopped_keys)} running service(s).",
            "stopped": stopped_keys,
        }

    def get_status(
        self,
        project_id: uuid.UUID | str,
        subsystem: str = "channel-app",
    ) -> dict[str, Any]:
        p_id = str(project_id)
        key = f"{p_id}_{subsystem}"
        info = self._processes.get(key)
        if not info:
            return {"status": "STOPPED", "project_id": p_id, "subsystem": subsystem}

        if info.process.poll() is not None:
            info.status = "STOPPED"

        return info.to_dict()

    def get_logs(
        self,
        project_id: uuid.UUID | str,
        subsystem: str = "channel-app",
        tail: int = 100,
    ) -> list[str]:
        p_id = str(project_id)
        key = f"{p_id}_{subsystem}"
        info = self._processes.get(key)
        if not info:
            return []
        lines = list(info.log_lines)
        return lines[-tail:] if tail else lines
