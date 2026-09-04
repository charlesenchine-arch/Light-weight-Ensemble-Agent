from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Mode = Literal["budget", "fast", "balanced", "quality"]
Intent = Literal[
    "implement",
    "fix",
    "refactor",
    "review",
    "design",
    "research",
    "plan",
    "explain",
]
Complexity = Literal["trivial", "standard", "hard"]
Domain = Literal[
    "backend",
    "frontend",
    "ui-design",
    "mobile",
    "devops",
    "data",
    "docs",
    "product",
    "architecture",
]
Role = Literal["router", "research", "plan", "design", "code", "review", "fix"]
ProviderName = Literal[
    "xai",
    "anthropic",
    "openai",
    "google",
    "deepseek",
    "moonshot",
    "qwen",
    "openrouter",
]


class TaskClass(BaseModel):
    intent: Intent = "implement"
    complexity: Complexity = "standard"
    domains: list[Domain] = Field(default_factory=list)
    needs_research: bool = False
    needs_plan: bool = True
    needs_design: bool = False
    needs_review: bool = True
    language: str = "zh"
    summary: str = ""


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    def add(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
        )


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    extra_content: dict[str, Any] | None = None


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    extra_content: dict[str, Any] | None = None


class ChatResult(BaseModel):
    message: ChatMessage
    usage: Usage = Field(default_factory=Usage)
    model: str = ""
    provider: str = ""
    raw_finish: str = "stop"


class ModelSpec(BaseModel):
    id: str
    provider: ProviderName
    openrouter_id: str | None = None
    input_per_m: float
    output_per_m: float
    cached_input_per_m: float | None = None
    context: int
    speed: Literal["fast", "medium", "slow"]
    quality: Literal["budget", "standard", "frontier"]
    strengths: list[str] = Field(default_factory=list)
    roles: list[Role] = Field(default_factory=list)
    notes: str = ""
    pricing_source: str
    pricing_verified: str
    status: Literal["active", "deprecated"] = "active"
    replacement: str | None = None


class Stage(BaseModel):
    role: Role
    model: ModelSpec
    reason: str
    max_steps: int = 12
    tools: Literal["none", "read", "all"] = "read"


class Pipeline(BaseModel):
    classification: TaskClass
    mode: Mode
    stages: list[Stage]
    estimated_usd: float = 0.0
    notes: list[str] = Field(default_factory=list)
