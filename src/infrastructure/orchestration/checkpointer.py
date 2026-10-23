import json
import sqlite3
import uuid
from typing import Any
from pathlib import Path
from sqlalchemy.orm import Session

from src.domain.workflow_state import WorkflowState
from src.infrastructure.db.models import WorkflowCheckpointORM, WorkflowRunORM


class WorkflowCheckpointService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_checkpoint(
        self,
        workflow_run_id: uuid.UUID,
        checkpoint_key: str,
        state: WorkflowState,
        version: int = 1,
    ) -> WorkflowCheckpointORM:
        state_dump = json.dumps(state, default=str)

        # Check if version exists to avoid constraint violation or increment
        existing = (
            self.db.query(WorkflowCheckpointORM)
            .filter_by(workflow_run_id=workflow_run_id, checkpoint_key=checkpoint_key, version=version)
            .first()
        )
        if existing:
            existing.state_data = state_dump
            checkpoint = existing
        else:
            checkpoint = WorkflowCheckpointORM(
                workflow_run_id=workflow_run_id,
                checkpoint_key=checkpoint_key,
                version=version,
                state_data=state_dump,
            )
            self.db.add(checkpoint)

        self.db.flush()
        return checkpoint

    def load_checkpoint(
        self,
        workflow_run_id: uuid.UUID,
        checkpoint_key: str,
        version: int = 1,
    ) -> WorkflowState | None:
        record = (
            self.db.query(WorkflowCheckpointORM)
            .filter_by(workflow_run_id=workflow_run_id, checkpoint_key=checkpoint_key, version=version)
            .first()
        )
        if not record:
            return None
        return json.loads(record.state_data)
