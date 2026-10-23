import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from src.domain.enums import ApprovalGateType, ApprovalStatus
from src.infrastructure.db.models import HumanApprovalORM


class ApprovalEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_approval_request(
        self,
        workflow_run_id: uuid.UUID,
        gate_type: ApprovalGateType | str,
        prompt_text: str,
    ) -> HumanApprovalORM:
        gate_str = gate_type.value if isinstance(gate_type, ApprovalGateType) else str(gate_type)

        approval = HumanApprovalORM(
            workflow_run_id=workflow_run_id,
            gate_type=gate_str,
            status=ApprovalStatus.PENDING.value,
            prompt_text=prompt_text,
        )
        self.db.add(approval)
        self.db.flush()
        return approval

    def resolve_approval(
        self,
        approval_id: uuid.UUID,
        approved: bool,
        reviewer_comments: str | None = None,
    ) -> HumanApprovalORM:
        approval = self.db.query(HumanApprovalORM).filter_by(id=approval_id).first()
        if not approval:
            raise ValueError(f"Approval request {approval_id} not found.")

        approval.status = ApprovalStatus.APPROVED.value if approved else ApprovalStatus.REJECTED.value
        approval.reviewer_comments = reviewer_comments
        approval.resolved_at = datetime.now(timezone.utc)

        self.db.flush()
        return approval
