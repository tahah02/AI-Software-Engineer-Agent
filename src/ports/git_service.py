import uuid
from typing import Any, Protocol, runtime_checkable

from src.domain.enums import RepositoryType


@runtime_checkable
class IGitService(Protocol):
    def initialize_repository(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
        target_framework: str = "generic",
    ) -> str:
        ...

    def get_repository_path(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
    ) -> str:
        ...

    def create_branch(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
        branch_name: str,
        base_branch: str = "develop",
    ) -> str:
        ...

    def checkout_branch(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
        branch_name: str,
    ) -> None:
        ...

    def commit_changes(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
        message: str,
    ) -> str:
        ...

    def get_current_commit_hash(
        self,
        project_id: uuid.UUID,
        repo_type: RepositoryType | str,
    ) -> str:
        ...

    def create_release_manifest(
        self,
        project_id: uuid.UUID,
        release_tag: str,
        test_run_id: uuid.UUID | None = None,
        security_scan_id: uuid.UUID | None = None,
    ) -> Any:
        ...
