import pytest
from src.api.routes.workflow import detect_target_framework, is_client_extension_intent


def test_detect_target_framework_universal():
    # Next.js / React
    assert detect_target_framework("Can you make a frontend of this on next.js?") == "TYPESCRIPT_NEXTJS"
    assert detect_target_framework("Create a React frontend with TypeScript and Tailwind") == "TYPESCRIPT_NEXTJS"

    # Vue / Nuxt
    assert detect_target_framework("Please build a Vue.js frontend for this API") == "VUE_NUXT"
    assert detect_target_framework("Create a Nuxt web application") == "VUE_NUXT"

    # Angular
    assert detect_target_framework("Build an Angular client portal") == "ANGULAR"

    # Svelte / SvelteKit
    assert detect_target_framework("Develop a SvelteKit dashboard") == "SVELTE"

    # Python / FastAPI
    assert detect_target_framework("Create a customer billing microservice with FastAPI") == "PYTHON_FASTAPI"

    # C# / .NET
    assert detect_target_framework("Build a Student Registration API with ASP.NET Core and EF Core") == "DOTNET_CSHARP"


def test_is_client_extension_intent():
    assert is_client_extension_intent("Can you make a frontend of this on next.js?") is True
    assert is_client_extension_intent("Build a rich React UI dashboard for student records") is True
    assert is_client_extension_intent("Add a mobile app client") is True
    assert is_client_extension_intent("Create a web portal") is True

    # Backend / pure API requests
    assert is_client_extension_intent("Build a Student Management CRUD API with ASP.NET Core and SQLite") is False
    assert is_client_extension_intent("Create a payment gateway webhook service in FastAPI") is False


def test_incremental_workflow_state_detection(tmp_path):
    # Setup mock workspace with existing channel-app backend
    workspace = tmp_path / "workspace" / "proj-123"
    channel_app = workspace / "channel-app"
    channel_app.mkdir(parents=True)
    (channel_app / "Program.cs").write_text("// backend code", encoding="utf-8")

    channel_app_exists = channel_app.exists() and any(channel_app.iterdir())
    user_requirement = "Can you make a frontend of this on next.js?"

    is_client_ext = is_client_extension_intent(user_requirement)
    is_incremental = bool(channel_app_exists and is_client_ext)
    subsystem_framework = detect_target_framework(user_requirement, default="TYPESCRIPT_NEXTJS")

    assert is_incremental is True
    assert subsystem_framework == "TYPESCRIPT_NEXTJS"
