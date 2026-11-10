from typing import Any

import os

import subprocess

import uuid

from pathlib import Path

from sqlalchemy.orm import Session

from src.domain.enums import RepositoryType

from src.infrastructure.config import Settings

from src.infrastructure.db.models import GitRepositoryORM, GitReleaseManifestORM

from src.ports.git_service import IGitService

GITIGNORE_TEMPLATES: dict[str, str] = {

    "python": (

        "__pycache__/\n"

        "*.py[cod]\n"

        "*$py.class\n"

        ".env\n"

        ".venv/\n"

        "env/\n"

        "*.log\n"

        ".pytest_cache/\n"

    ),

    "csharp": (

        "bin/\n"

        "obj/\n"

        "*.user\n"

        "*.suo\n"

        ".vs/\n"

        "*.log\n"

    ),

    "typescript": (

        "node_modules/\n"

        "dist/\n"

        ".next/\n"

        "npm-debug.log*\n"

        "yarn-debug.log*\n"

        "yarn-error.log*\n"

        ".env\n"

    ),

    "generic": (

        ".env\n"

        "*.log\n"

        ".DS_Store\n"

        "Thumbs.db\n"

    ),

}

class GitService(IGitService):

    def __init__(self, db: Session, base_workspace_dir: str = "./workspace") -> None:

        self.db = db

        self.base_workspace_dir = Path(base_workspace_dir).resolve()

    def _run_git(self, repo_path: Path, args: list[str]) -> subprocess.CompletedProcess:

        # Enforce local git commands with safe defaults

        cmd = ["git"] + args

        env = {

            **os.environ,

            "GIT_AUTHOR_NAME": "AAISE Orchestrator",

            "GIT_AUTHOR_EMAIL": "aaise@local.internal",

            "GIT_COMMITTER_NAME": "AAISE Orchestrator",

            "GIT_COMMITTER_EMAIL": "aaise@local.internal",

        }

        env["GIT_TERMINAL_PROMPT"] = "0"

        res = subprocess.run(

            cmd,

            cwd=str(repo_path),

            capture_output=True,

            text=True,

            encoding="utf-8",

            errors="replace",

            env=env,

            check=True,

            timeout=45,

        )

        return res

    def get_repository_path(

        self,

        project_id: uuid.UUID,

        repo_type: RepositoryType | str,

    ) -> str:

        type_str = (repo_type.value if isinstance(repo_type, RepositoryType) else str(repo_type)).lower()

        repo_dir_name = "channel-app" if "channel" in type_str else "mock-vendor-api"

        return str(self.base_workspace_dir / str(project_id) / repo_dir_name)

    init_repository = None  # defined below
    def initialize_repository(

        self,

        project_id: uuid.UUID,

        repo_type: RepositoryType | str,

        target_framework: str = "generic",

    ) -> str:

        type_str = repo_type.value if isinstance(repo_type, RepositoryType) else str(repo_type).upper()

        repo_path_str = self.get_repository_path(project_id, repo_type)

        repo_path = Path(repo_path_str)

        # Create directory safely

        repo_path.mkdir(parents=True, exist_ok=True)

        # Initialize git repo if not already initialized

        if not (repo_path / ".git").exists():

            self._run_git(repo_path, ["init", "-b", "main"])

            # Setup .gitignore

            framework_key = target_framework.lower()

            if any(k in framework_key for k in ("py", "python", "fastapi", "django", "flask")):

                tpl = GITIGNORE_TEMPLATES["python"]

            elif any(k in framework_key for k in ("cs", "csharp", "net", "dotnet")):

                tpl = GITIGNORE_TEMPLATES["csharp"]

            elif any(k in framework_key for k in ("type", "script", "js", "react", "next", "node")):

                tpl = GITIGNORE_TEMPLATES["typescript"]

            else:

                tpl = GITIGNORE_TEMPLATES["generic"]

            (repo_path / ".gitignore").write_text(tpl, encoding="utf-8")

            (repo_path / "README.md").write_text(

                f"# Project Repository\n\nType: {type_str}\nProject ID: {project_id}\n",

                encoding="utf-8",

            )

            # Initial commit on main

            self._run_git(repo_path, ["add", "."])

            self._run_git(repo_path, ["commit", "-m", "chore: initial repository structure"])

            # Create develop branch

            self._run_git(repo_path, ["checkout", "-b", "develop"])

        # Persist record in database if not already tracked

        existing = (

            self.db.query(GitRepositoryORM)

            .filter_by(project_id=project_id, repo_type=type_str)

            .first()

        )

        if not existing:

            repo_record = GitRepositoryORM(

                project_id=project_id,

                repo_type=type_str,

                local_path=str(repo_path),

            )

            self.db.add(repo_record)

            self.db.flush()

        return str(repo_path)

    init_repository = initialize_repository

    def create_branch(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
        branch_name: str,
        base_branch: str = "develop",
    ) -> str:
        repo_path = Path(self.get_repository_path(project_id, repo_type))
        if not (repo_path / ".git").exists():
            raise FileNotFoundError(f"Repository not initialized at {repo_path}")

        try:
            status_res = self._run_git(repo_path, ["status", "--porcelain"])
            if status_res.stdout.strip():
                self._run_git(repo_path, ["add", "-A"])
                self._run_git(repo_path, ["commit", "-m", "chore: auto-save before branching"])
        except Exception:
            pass

        try:
            self._run_git(repo_path, ["checkout", "-B", branch_name])
        except Exception:
            try:
                self._run_git(repo_path, ["checkout", branch_name])
            except Exception:
                pass
        return branch_name

    def checkout_branch(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
        branch_name: str,
    ) -> None:
        repo_path = Path(self.get_repository_path(project_id, repo_type))
        if not (repo_path / ".git").exists():
            return

        try:
            status_res = self._run_git(repo_path, ["status", "--porcelain"])
            if status_res.stdout.strip():
                self._run_git(repo_path, ["add", "-A"])
                self._run_git(repo_path, ["commit", "-m", "chore: auto-save before checkout"])
        except Exception:
            pass

        try:
            self._run_git(repo_path, ["checkout", branch_name])
        except Exception:
            try:
                self._run_git(repo_path, ["checkout", "-B", branch_name])
            except Exception:
                pass

    def commit_changes(

        self,

        project_id: uuid.UUID,

        repo_type: RepositoryType | str,

        message: str,

    ) -> str:

        # Validate Conventional Commits format

        valid_prefixes = ("feat:", "fix:", "chore:", "docs:", "test:", "sec:", "refactor:")

        if not any(message.strip().startswith(p) for p in valid_prefixes):

            raise ValueError(

                f"Commit message must follow Conventional Commits ({', '.join(valid_prefixes)}). Given: {message}"

            )

        repo_path = Path(self.get_repository_path(project_id, repo_type))

        if not (repo_path / ".git").exists():

            raise FileNotFoundError(f"Repository not initialized at {repo_path}")

        self._run_git(repo_path, ["add", "."])

        try:
            self._run_git(repo_path, ["commit", "-m", message])
        except Exception:
            pass

        return self.get_current_commit_hash(project_id, repo_type)

    def get_current_commit_hash(

        self,

        project_id: uuid.UUID,

        repo_type: RepositoryType | str,

    ) -> str:

        repo_path = Path(self.get_repository_path(project_id, repo_type))

        if not (repo_path / ".git").exists():

            raise FileNotFoundError(f"Repository not initialized at {repo_path}")

        res = self._run_git(repo_path, ["rev-parse", "HEAD"])

        return res.stdout.strip()

    def create_release_manifest(

        self,

        project_id: uuid.UUID,

        release_tag: str,

        test_run_id: uuid.UUID | None = None,

        security_scan_id: uuid.UUID | None = None,

    ) -> GitReleaseManifestORM:

        # channel-app commit hash is mandatory

        channel_hash = self.get_current_commit_hash(project_id, RepositoryType.CHANNEL_APP)

        # mock-vendor-api commit hash is optional (depends on whether Agent 2 was enabled)

        mock_hash = None

        mock_path = Path(self.get_repository_path(project_id, RepositoryType.MOCK_VENDOR_API))

        if (mock_path / ".git").exists():

            mock_hash = self.get_current_commit_hash(project_id, RepositoryType.MOCK_VENDOR_API)

        manifest = GitReleaseManifestORM(

            project_id=project_id,

            release_tag=release_tag,

            channel_commit_hash=channel_hash,

            mock_commit_hash=mock_hash,

            test_run_id=test_run_id,

            security_scan_id=security_scan_id,

        )

        self.db.add(manifest)

        self.db.flush()

        return manifest

    def push_to_remote(

        self,

        project_id: uuid.UUID,

        repo_type: RepositoryType | str,

        remote_url: str,

        branch_name: str | None = None,

    ) -> dict[str, Any]:

        repo_path = Path(self.get_repository_path(project_id, repo_type))

        if not (repo_path / ".git").exists():

            raise FileNotFoundError(f"Repository not initialized at {repo_path}")

        # Ensure clean remote URL format

        remote_url = remote_url.strip()

        # Check existing remotes

        remotes_res = self._run_git(repo_path, ["remote"])

        existing_remotes = [r.strip() for r in remotes_res.stdout.splitlines() if r.strip()]

        if "origin" in existing_remotes:

            self._run_git(repo_path, ["remote", "set-url", "origin", remote_url])

        else:

            self._run_git(repo_path, ["remote", "add", "origin", remote_url])

        # Get current branch if not specified

        if not branch_name:

            branch_res = self._run_git(repo_path, ["branch", "--show-current"])

            branch_name = branch_res.stdout.strip() or "main"

        try:

            push_res = self._run_git(repo_path, ["push", "-u", "origin", branch_name])

            output = push_res.stdout or push_res.stderr or "Pushed successfully."

            return {

                "success": True,

                "remote_url": remote_url,

                "branch": branch_name,

                "output": output.strip(),

            }

        except subprocess.CalledProcessError as e:

            err_msg = e.stderr or e.stdout or str(e)

            return {

                "success": False,

                "remote_url": remote_url,

                "branch": branch_name,

                "error": err_msg.strip(),

            }

    def get_diff(self, project_id: uuid.UUID, repo_type: RepositoryType | str) -> str:

        repo_path = Path(self.get_repository_path(project_id, repo_type))

        if not (repo_path / ".git").exists():

            return ""

        try:

            res = self._run_git(repo_path, ["diff", "HEAD~1", "HEAD"])

            if not res.stdout.strip():

                res = self._run_git(repo_path, ["diff"])

            return res.stdout

        except Exception:

            return ""

    def get_all_branches(self, project_id: uuid.UUID, repo_type: RepositoryType | str) -> list[str]:

        repo_path = Path(self.get_repository_path(project_id, repo_type))

        if not (repo_path / ".git").exists():

            return ["develop"]

        try:

            res = self._run_git(repo_path, ["branch", "--list"])

            branches = [b.strip().lstrip("* ").strip() for b in res.stdout.splitlines() if b.strip()]

            return branches if branches else ["develop"]

        except Exception:

            return ["develop"]

    def get_current_branch(self, project_id: uuid.UUID, repo_type: RepositoryType | str) -> str | None:

        repo_path = Path(self.get_repository_path(project_id, repo_type))

        if not (repo_path / ".git").exists():

            return "develop"

        try:

            res = self._run_git(repo_path, ["branch", "--show-current"])

            cur = res.stdout.strip()

            return cur if cur else "develop"

        except Exception:

            return "develop"
