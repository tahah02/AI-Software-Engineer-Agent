import json
import uuid
from sqlalchemy.orm import Session
from src.infrastructure.db.models import ConversationORM, MessageORM


def save_chat_message(
    db: Session,
    project_id: uuid.UUID,
    sender_type: str,
    content: str,
    agent_id: str | None = None,
    metadata: dict | None = None,
) -> MessageORM:
    conv = db.query(ConversationORM).filter_by(project_id=project_id).first()
    if not conv:
        conv = ConversationORM(project_id=project_id, title=str(project_id))
        db.add(conv)
        db.flush()

    msg = MessageORM(
        conversation_id=conv.id,
        sender_type=sender_type,
        agent_id=agent_id,
        content=content,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(msg)
    db.commit()
    return msg
