import re
import traceback

from typing import Any

from utils.Builder import build
from utils.Logs import ExceptionLog
from utils.Profile import get_db_profile
from utils.Pool import StandardDatabasesConnectPool
from dto.StandardDBTemplate import StandardDBStepStruct
from utils.Manager import StandardDatabasesConnPoolFactory
from dto.StandardLayerResponseTemplate import StandardLayerStructTemplate

_FACTORY: StandardDatabasesConnPoolFactory = StandardDatabasesConnPoolFactory()

def _get_pool(profile: str) -> StandardDatabasesConnectPool | None:
    """根据 profile 获取连接池"""
    mapping = get_db_profile(profile)
    if not mapping: return
    return _FACTORY.get_pool(
        sys=mapping["system"],
        db_typ=mapping["db_type"],
        env="dev",
    )

def _to_oracle_sql(sql: str) -> str: return re.sub(r"%\((\w+)\)s", r":\1", sql)

def _execute(step: StandardDBStepStruct) -> StandardLayerStructTemplate[Any]:
    """
    统一执行入口。
    """
    pool = _get_pool(step.profile)
    if not pool:
        ExceptionLog.error("[DB] 获取连接池失败, profile: %s", step.profile)
        return StandardLayerStructTemplate.error(f"获取数据库连接池失败: {step.profile}")

    built = build(step)
    if built.is_error: return StandardLayerStructTemplate.error(built.message or "SQL 构建失败")
    sql, params = built.data or ("", {})
    mapping = get_db_profile(step.profile)
    if mapping and mapping.get("db_type") == "oracle": sql: str = _to_oracle_sql(sql)
    ExceptionLog.info("[DB] %s → %s | %s", step.action, step.table, sql)
    try:
        result = pool.query(sql, params)
        return StandardLayerStructTemplate.ok(result)
    except Exception:
        ExceptionLog.error("[DB] %s 失败 | %s", step.action, traceback.format_exc())
        return StandardLayerStructTemplate.error(f"数据库操作异常: {step.action}")

def exec_select(step: StandardDBStepStruct) -> StandardLayerStructTemplate[list[dict]]: return _execute(step)
def exec_create(step: StandardDBStepStruct) -> StandardLayerStructTemplate[None]: return _execute(step)
def exec_update(step: StandardDBStepStruct) -> StandardLayerStructTemplate[None]: return _execute(step)
def exec_delete(step: StandardDBStepStruct) -> StandardLayerStructTemplate[None]:return _execute(step)

_STEP_EXECUTOR: dict[str, Any] = {
    "SELECT": exec_select,
    "CREATE": exec_create,
    "UPDATE": exec_update,
    "DELETE": exec_delete,
}

def exec_step(step: StandardDBStepStruct) -> StandardLayerStructTemplate[Any]:
    """路由入口：根据 action 自动分发"""
    func = _STEP_EXECUTOR.get(step.action.upper())
    if func: return func(step)
    else:
        ExceptionLog.error("[DB] 未知操作: %s", step.action)
        return StandardLayerStructTemplate.fail(f"未知数据库操作: {step.action}")
