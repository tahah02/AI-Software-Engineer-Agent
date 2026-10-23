import os
from pathlib import Path
from src.ports.llm_gateway import ToolDefinition, ToolParameterSchema


def get_file_read_tool() -> ToolDefinition:
    return ToolDefinition(
        name="read_file",
        description="Reads the complete text content of a file relative to workspace.",
        parameters=ToolParameterSchema(
            type="object",
            properties={
                "relative_path": {
                    "type": "string",
                    "description": "Path to file relative to workspace root.",
                }
            },
            required=["relative_path"],
        ),
    )


def get_file_write_tool() -> ToolDefinition:
    return ToolDefinition(
        name="write_file",
        description="Creates or overwrites a file relative to workspace.",
        parameters=ToolParameterSchema(
            type="object",
            properties={
                "relative_path": {
                    "type": "string",
                    "description": "Path to file relative to workspace root.",
                },
                "content": {
                    "type": "string",
                    "description": "Full text content to write.",
                },
            },
            required=["relative_path", "content"],
        ),
    )


def get_list_files_tool() -> ToolDefinition:
    return ToolDefinition(
        name="list_files",
        description="Lists all files in a directory relative to workspace.",
        parameters=ToolParameterSchema(
            type="object",
            properties={
                "relative_path": {
                    "type": "string",
                    "description": "Directory path relative to workspace root (defaults to empty for root).",
                }
            },
            required=[],
        ),
    )


def execute_file_read(workspace_path: str, relative_path: str) -> str:
    path = (Path(workspace_path) / relative_path).resolve()
    ws_resolved = Path(workspace_path).resolve()
    if not str(path).startswith(str(ws_resolved)):
        raise PermissionError(f"Access denied: Path {path} outside workspace.")
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {relative_path}")
    return path.read_text(encoding="utf-8")


def execute_file_write(workspace_path: str, relative_path: str, content: str) -> str:
    path = (Path(workspace_path) / relative_path).resolve()
    ws_resolved = Path(workspace_path).resolve()
    if not str(path).startswith(str(ws_resolved)):
        raise PermissionError(f"Access denied: Path {path} outside workspace.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Successfully wrote {len(content)} characters to {relative_path}"


def execute_list_files(workspace_path: str, relative_path: str = "") -> list[str]:
    path = (Path(workspace_path) / relative_path).resolve()
    ws_resolved = Path(workspace_path).resolve()
    if not str(path).startswith(str(ws_resolved)):
        raise PermissionError(f"Access denied: Path {path} outside workspace.")
    if not path.exists():
        return []
    items: list[str] = []
    for root, _, files in os.walk(path):
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(ws_resolved)
            # Skip .git files
            if ".git" not in rel.parts:
                items.append(str(rel).replace("\\", "/"))
    return items
