import uuid
from src.infrastructure.db.session import SessionLocal
from src.infrastructure.db.models import ProjectORM, ProjectAgentConfigORM

def seed():
    db = SessionLocal()
    existing = db.query(ProjectORM).all()
    if existing:
        print("Already seeded:", len(existing))
        return

    projects_data = [
        ("Bank API", "Core banking API with JWT and account services", "PYTHON_FASTAPI"),
        ("SME Portal", "Small business banking portal with vendor integration", "PYTHON_FASTAPI"),
        ("Fintech App", "Mobile fintech payment backend", "PYTHON_FASTAPI"),
        ("Document AI", "Automated invoice and OCR processing service", "PYTHON_FASTAPI"),
    ]

    for name, desc, framework in projects_data:
        proj_id = uuid.uuid4()
        p = ProjectORM(id=proj_id, name=name, description=desc, target_framework=framework, status="ACTIVE")
        db.add(p)
        db.flush()

        # Seed 5 agents for this project
        agents = [
            ("AGENT_1", True, "gemini", "gemini-3.8-flash"),
            ("AGENT_2", True, "groq", "openai/gpt-oss-120b"),
            ("AGENT_3", True, "ollama", "qwen2.5-coder:7b"),
            ("AGENT_4", True, "groq", "qwen/qwen3.8-27b"),
            ("AGENT_5", True, "gemini", "gemini-3.5-flash-lite"),
        ]
        for atype, is_en, prov, model in agents:
            cfg = ProjectAgentConfigORM(
                project_id=proj_id,
                agent_type=atype,
                is_enabled=is_en,
                provider=prov,
                model_name=model,
            )
            db.add(cfg)

    db.commit()
    print("Database seeded successfully with 4 sample projects and agent configs!")

if __name__ == "__main__":
    seed()
