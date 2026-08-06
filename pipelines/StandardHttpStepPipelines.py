from typing import Any

from tools.Re import resolve_data
from utils.Request import req_meta
from core.StandardStepPipeline import register_step_pipeline
from dto.StandardHttpTemplate import StandardReqYAMLSetStruct
from dto.StandardYAMLAnalysisTemplate import StandardStepResult
from dto.StandardStepPipelineTemplate import StepPipelineContext
from pipelines.StandardPublicStepPipelines import (
    step_db_setup,
    step_extract,
    step_validate,
    step_db_checks,
    step_finalize,
)

"""
HTTP 专属 pipeline 步骤 + 内置组合注册。

内置组合:
  http           — db_setup → [HTTP → extract → validate] → db_checks(默认, 保持现行为)
  db_before_http — 同 http, 语义化的显式别名
  http_before_db — [HTTP → extract → validate] → db_setup → db_checks
  db             — 纯 DB 步骤(db_setup → db_checks), 无需 HTTP
"""

def _http_op(req_resolved: dict, resp_data: dict | None, error: str | None, passed: bool) -> dict:
    """构建 HTTP 操作痕迹记录, 供报告展示。"""
    return {
        "type": "http",
        "method": req_resolved.get("method"),
        "path": req_resolved.get("path"),
        "url": (resp_data or {}).get("url"),
        "status_code": (resp_data or {}).get("status_code"),
        "elapsed": (resp_data or {}).get("elapsed"),
        "request": req_resolved,
        "response": resp_data,
        "error": error,
        "passed": passed,
    }

# ═══════════════════════════════════════════════════════════════
#  step_send_request: resolve 请求占位符 + 发送 HTTP 请求
#  异常 / error → 短路返回 failed 结果(操作痕迹一并带出)
# ═══════════════════════════════════════════════════════════════
async def step_send_request(ctx: StepPipelineContext) -> StandardStepResult | None:
    if not ctx.step.request:
        return None
    ctx.stages.add("request")

    req_dict: dict = ctx.step.request.model_dump()
    req_resolved_data: dict = resolve_data(req_dict, ctx.pool)
    ctx.http.req_resolved = req_resolved_data

    try:
        req_struct: StandardReqYAMLSetStruct = StandardReqYAMLSetStruct.from_dict(req_resolved_data)
        result = await req_meta(
            data=req_struct, base_url=ctx.base_url, timeout=ctx.timeout
        )
    except Exception as exc:
        op: dict = _http_op(req_resolved_data, None, str(exc), False)
        ctx.operations.append(op)
        return StandardStepResult(
            name=ctx.step.name,
            passed=False,
            errors=[f"请求异常: {exc}"],
            operations=[op],
        )

    if result.is_error:
        op = _http_op(req_resolved_data, None, result.message or "请求失败", False)
        ctx.operations.append(op)
        return StandardStepResult(
            name=ctx.step.name,
            passed=False,
            errors=[result.message or "请求失败"],
            operations=[op],
        )

    ctx.http.resp_data = result.data or {}
    ctx.http.status_code = ctx.http.resp_data.get("status_code")
    resp_body: Any = ctx.http.resp_data.get("body", {})
    ctx.http.resp_json = resp_body if isinstance(resp_body, dict) else {}
    ctx.operations.append(_http_op(req_resolved_data, ctx.http.resp_data, None, True))
    return None


def install() -> None:
    """注册内置 step pipeline 组合。由 core.StandardStepPipeline.ensure_installed 调用。"""
    _default_http: tuple = (
        step_db_setup, step_send_request, step_extract,
        step_validate, step_db_checks, step_finalize,
    )
    register_step_pipeline("http", _default_http)
    register_step_pipeline("db_before_http", _default_http)
    register_step_pipeline("http_before_db", (
        step_send_request, step_extract, step_validate,
        step_db_setup, step_db_checks, step_finalize,
    ))
    register_step_pipeline("db", (
        step_db_setup, step_db_checks, step_finalize,
    ))
