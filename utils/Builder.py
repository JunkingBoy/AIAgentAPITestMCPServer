from typing import Any

from utils.Logs import ExceptionLog
from dto.StandardDBTemplate import StandardDBStepStruct
from dto.StandardLayerResponseTemplate import StandardLayerStructTemplate

def build(step: StandardDBStepStruct) -> StandardLayerStructTemplate[tuple[str, dict[str, Any]]]:
    match step.action.upper():
        case "SELECT": return StandardLayerStructTemplate.ok(_build_select(step))
        case "CREATE": return StandardLayerStructTemplate.ok(_build_insert(step))
        case "UPDATE": return StandardLayerStructTemplate.ok(_build_update(step))
        case "DELETE": return StandardLayerStructTemplate.ok(_build_delete(step))
        case _:
            ExceptionLog.error("[Builder] 不支持的动作: %s", step.action)
            return StandardLayerStructTemplate.fail(f"不支持的数据操作: {step.action}")

def _build_select(step: StandardDBStepStruct) -> tuple[str, dict]:
    fields_str: str = ", ".join(step.fields) if step.fields else "*"
    where_sql, params = _build_where(step.where or {})
    return f"SELECT {fields_str} FROM {step.table}{where_sql}", params

def _build_insert(step: StandardDBStepStruct) -> tuple[str, dict]:
    """INSERT INTO table (f1, f2) VALUES (%(f1)s, %(f2)s)"""
    fields: list[str] = step.fields or []
    where: dict = step.where or {}
    columns = ", ".join(fields)
    placeholders = ", ".join(f"%({f})s" for f in fields)
    params = {f: where.get(f) for f in fields}
    return f"INSERT INTO {step.table} ({columns}) VALUES ({placeholders})", params

def _build_update(step: StandardDBStepStruct) -> tuple[str, dict]:
    """UPDATE table SET f1=%(f1)s WHERE id=%(id)s"""
    fields: list[str] = step.fields or []
    where: dict = step.where or {}
    set_clause = ", ".join(f"{f}=%({f})s" for f in fields)
    set_params = {f: where.get(f) for f in fields}
    # 剩余的 where 条件做过滤
    where_cond = {k: where[k] for k in where if k not in fields}
    where_sql, where_params = _build_where(where_cond)
    params = {**set_params, **where_params}
    return f"UPDATE {step.table} SET {set_clause}{where_sql}", params

def _build_delete(step: StandardDBStepStruct) -> tuple[str, dict]:
    where_sql, params = _build_where(step.where or {})
    return f"DELETE FROM {step.table}{where_sql}", params

def _build_where(where: dict) -> tuple[str, dict]:
    if not where: return "", {}
    clauses = [f"{k}=%({k})s" for k in where]
    return f" WHERE {' AND '.join(clauses)}", dict(where)
