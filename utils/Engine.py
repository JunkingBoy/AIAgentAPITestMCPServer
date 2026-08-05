from typing import Any

from dto.StandardHttpTemplate import StandardReqYAMLSetStruct
from dto.StandardYAMLAnalysisTemplate import (
    StandardFlowMetaStruct,
    StandardStepRawStruct,
)

def jsonpath_get(data: dict | list, expr: str) -> Any:
    """支持 $.data.token / $.data.items.0.id 等点号路径"""
    if not expr.startswith("$."): return None
    keys: list[str] = expr[2:].split(".")
    current: Any = data
    for key in keys:
        match current:
            case dict(): current = current.get(key)
            case list() if key.isdigit():
                idx: int = int(key)
                current = current[idx] if 0 <= idx < len(current) else None
            case _: return
        if not current: return
    return current

def parse_meta(resolved: dict) -> StandardFlowMetaStruct:
    return StandardFlowMetaStruct(
        name=resolved.get("name", ""),
        description=resolved.get("description"),
        base_url=resolved.get("base_url", ""),
        timeout=resolved.get("timeout"),
        variables=resolved.get("variables", {}),
    )

def parse_steps(resolved: dict) -> list[StandardStepRawStruct]:
    steps_raw: list[dict] = resolved.get("steps", [])
    steps: list[StandardStepRawStruct] = []

    for sd in steps_raw:
        req_data: dict | None = sd.get("request")
        request: StandardReqYAMLSetStruct | None = (
            StandardReqYAMLSetStruct.from_dict(req_data) if req_data else None
        )

        step: StandardStepRawStruct = StandardStepRawStruct(
            name=sd.get("name", ""),
            request=request,
            db_setup=sd.get("db_setup"),
            db_checks=sd.get("db_checks"),
            extract=sd.get("extract"),
            validations=sd.get("validate"),
        )
        steps.append(step)

    return steps
