"""Tool catalogue endpoint (read-only)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.dependencies import get_tool_registry

router = APIRouter(prefix="/v1", tags=["tools"])


class ToolInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    arguments_schema: dict


class ToolListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tools: list[ToolInfo]


@router.get("/tools", response_model=ToolListResponse)
def list_tools() -> ToolListResponse:
    registry = get_tool_registry()
    return ToolListResponse(
        tools=[
            ToolInfo(
                name=t.name,
                description=t.description,
                arguments_schema=t.arguments_schema,
            )
            for t in registry.all_tools()
        ]
    )