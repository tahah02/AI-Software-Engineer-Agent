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
        res = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            env=env,
            check=True,
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

        # Checkout base branch first to branch off correctly
        self._run_git(repo_path, ["checkout", base_branch])
        self._run_git(repo_path, ["checkout", "-b", branch_name])
        return branch_name

    def checkout_branch(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
        branch_name: str,
    ) -> None:
        repo_path = Path(self.get_repository_path(project_id, repo_type))
        if not (repo_path / ".git").exists():
            raise FileNotFoundError(f"Repository not initialized at {repo_path}")

        self._run_git(repo_path, ["checkout", branch_name])

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
        self._run_git(repo_path, ["commit", "-m", message])
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
