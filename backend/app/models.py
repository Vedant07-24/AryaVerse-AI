

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class SpecRequest(BaseModel):
    source: str = Field(..., description="OpenAPI URL or JSON/YAML text")

class GoalRequest(BaseModel):
    goal: str
    auth: Dict[str, str] = {}
    max_steps: int = 3

class PlanStep(BaseModel):
    operation_id: str
    method: str
    path: str
    reason: str
    parameter_map: Dict[str, Any] = {}
    depends_on: Optional[str] = None

class Plan(BaseModel):
    goal: str
    reasoning: str
    steps: List[PlanStep]
    mode: str = "local"

class ExecuteRequest(BaseModel):
    goal: str
    spec: Dict[str, Any]
    auth: Dict[str, str] = {}
    max_steps: int = 3
