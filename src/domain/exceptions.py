class AAISEException(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EntityNotFoundError(AAISEException):
    def __init__(self, entity_name: str, entity_id: str) -> None:
        super().__init__(f"{entity_name} with ID '{entity_id}' not found.")
        self.entity_name = entity_name
        self.entity_id = entity_id


class ValidationError(AAISEException):
    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"Validation failed on '{field}': {reason}")
        self.field = field
        self.reason = reason


class WorkflowStateError(AAISEException):
    def __init__(self, current_phase: str, action: str) -> None:
        super().__init__(f"Cannot perform action '{action}' during phase '{current_phase}'.")
        self.current_phase = current_phase
        self.action = action


class ApprovalPendingError(AAISEException):
    def __init__(self, gate_type: str, approval_id: str) -> None:
        super().__init__(f"Action blocked by pending human approval gate '{gate_type}' (ID: {approval_id}).")
        self.gate_type = gate_type
        self.approval_id = approval_id
