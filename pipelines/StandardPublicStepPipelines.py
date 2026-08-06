from typing import Any

from tools.Re import resolve_data
from utils.Engine import jsonpath_get
from utils.Executor import exec_step as exec_db_step
from dto.StandardDBTemplate import StandardDBStepStruct
from dto.StandardYAMLAnalysisTemplate import StandardStepResult
from dto.StandardStepPipelineTemplate import StepPipelineContext

"""
可复用的公共 pipeline 步骤 — 与具体请求无关, 可自由组合进任意 pipeline。
所有步骤签名: async (ctx: StepPipelineContext) -> StandardStepResult | None
  None = 继续, StandardStepResult = 短路返回。
"""

def _db_op(op_type: str, struct: StandardDBStepStruct, rows: list[dict] | None,
           error: str | None, passed: bool) -> dict:
    """构建 DB 操作痕迹记录, 供报告展示。rows 含 Decimal/datetime 等, 序列化交给报告层。"""
    return {
        "type": op_type,
        "profile": struct.profile,
        "table": struct.table,
        "action": struct.action.upper() if struct.action else "",
        "fields": struct.fields,
        "where": struct.where,
        "inject": struct.inject,
        "expected": struct.expected,
        "rows_count": len(rows) if rows else 0,
        "row_preview": rows[:5] if rows else None,
        "error": error,
        "passed": passed,
    }

# ═══════════════════════════════════════════════════════════════
#  db_setup: 执行前置 SQL + inject 回填变量池
#  失败 → 短路返回 failed 结果
# ═══════════════════════════════════════════════════════════════
async def step_db_setup(ctx: StepPipelineContext) -> StandardStepResult | None:
    if not ctx.step.db_setup:
        return None
    ctx.stages.add("db_setup")

    for ds_dict in ctx.step.db_setup:
        ds_resolved: dict = resolve_data(ds_dict, ctx.pool)
        ds_struct: StandardDBStepStruct = StandardDBStepStruct.from_dict(ds_resolved)
        ds_result = exec_db_step(ds_struct)
        rows: list[dict] = ds_result.data or []
        if ds_result.is_error:
            ctx.db.setup_ok = False
            ctx.db.setup_error = ds_result.message
            op: dict = _db_op("db_setup", ds_struct, None, ds_result.message, False)
            ctx.operations.append(op)
            return StandardStepResult(
                name=ctx.step.name,
                passed=False,
                errors=[f"db_setup 失败: {ds_result.message}"],
                operations=[op],   # 短路结果同样带出操作痕迹
            )
        ctx.operations.append(_db_op("db_setup", ds_struct, rows, None, True))
        # inject: 把查询结果第一行的指定列写入运行时变量池, 供本步后续或后续步骤引用
        if ds_struct.inject and rows:
            first_row: dict = rows[0]
            for var_name, column in ds_struct.inject.items():
                value: Any = (
                    jsonpath_get(first_row, column)
                    if column.startswith("$.")
                    else first_row.get(column)
                )
                if value is not None:
                    ctx.pool.set_runtime(var_name, value)
                    ctx.extract.extracted[var_name] = value

    return None

# ═══════════════════════════════════════════════════════════════
#  extract: 从响应 body 按 jsonpath 提取变量写入变量池
#  恒 None(无失败语义)
# ═══════════════════════════════════════════════════════════════
async def step_extract(ctx: StepPipelineContext) -> StandardStepResult | None:
    if not ctx.step.extract:
        return None
    ctx.stages.add("extract")

    for var_name, jsonpath_expr in ctx.step.extract.items():
        value: Any = jsonpath_get(ctx.http.resp_json, jsonpath_expr)
        if value is not None:
            ctx.pool.set_runtime(var_name, value)
            ctx.extract.extracted[var_name] = value

    return None

# ═══════════════════════════════════════════════════════════════
#  validate: 校验 status_code / $.路径 断言
#  恒 None(累积错误继续执行, 让 db_checks 仍运行)
# ═══════════════════════════════════════════════════════════════
async def step_validate(ctx: StepPipelineContext) -> StandardStepResult | None:
    if not ctx.step.validations:
        return None
    ctx.stages.add("validate")

    for v in ctx.step.validations:
        check: str = v.get("check", "")
        assert_type: str = v.get("assert", "equals")   # 目前只支持 equals
        expected: Any = v.get("value")

        if check == "status_code":
            if ctx.http.status_code != expected:
                ctx.validate.passed = False
                ctx.validate.errors.append(
                    f"状态码断言失败: 期望 {expected}, 实际 {ctx.http.status_code}"
                )

        elif check.startswith("$."):
            actual: Any = jsonpath_get(ctx.http.resp_json, check)
            if actual != expected:
                ctx.validate.passed = False
                ctx.validate.errors.append(
                    f"{check} 断言失败: 期望 {expected}, 实际 {actual}"
                )

    return None

# ═══════════════════════════════════════════════════════════════
#  db_checks: 后置 SQL 校验(expected: true 要求有数据 / false 要求无数据)
#  恒 None(累积错误继续执行)
# ═══════════════════════════════════════════════════════════════
async def step_db_checks(ctx: StepPipelineContext) -> StandardStepResult | None:
    if not ctx.step.db_checks:
        return None
    ctx.stages.add("db_checks")

    for dc_dict in ctx.step.db_checks:
        dc_dict.setdefault("action", "SELECT")
        dc_resolved: dict = resolve_data(dc_dict, ctx.pool)
        dc_struct: StandardDBStepStruct = StandardDBStepStruct.from_dict(dc_resolved)
        dc_result = exec_db_step(dc_struct)
        rows: list[dict] = dc_result.data or []

        if dc_result.is_error:
            ctx.db.checks_ok = False
            ctx.db.check_errors.append(f"db_checks 查询失败: {dc_result.message}")
            ctx.operations.append(_db_op("db_checks", dc_struct, None, dc_result.message, False))
        elif dc_struct.expected is not None:
            if dc_struct.expected and not rows:
                ctx.db.checks_ok = False
                err: str = f"db_checks 预期有数据, 但 {dc_struct.table} 查询无结果"
                ctx.db.check_errors.append(err)
                ctx.operations.append(_db_op("db_checks", dc_struct, rows, err, False))
            elif not dc_struct.expected and rows:
                ctx.db.checks_ok = False
                err = f"db_checks 预期无数据, 但 {dc_struct.table} 返回 {len(rows)} 条"
                ctx.db.check_errors.append(err)
                ctx.operations.append(_db_op("db_checks", dc_struct, rows, err, False))
            else:
                ctx.operations.append(_db_op("db_checks", dc_struct, rows, None, True))
        else:
            # expected 未设置 → 不校验, 仍记录操作
            ctx.operations.append(_db_op("db_checks", dc_struct, rows, None, True))

    return None

# ═══════════════════════════════════════════════════════════════
#  finalize: 汇总所有子上下文 → 构建 StandardStepResult
#  恒返回结果(终止链)
# ═══════════════════════════════════════════════════════════════
async def step_finalize(ctx: StepPipelineContext) -> StandardStepResult:
    errors: list[str] = list(ctx.validate.errors)
    errors.extend(ctx.db.check_errors)

    # 覆盖校验: step 提供了某字段, 但所选 pipeline 未执行对应阶段 → 配置错误
    _coverage: list[tuple[str, list[str]]] = [
        ("request",     ["request"]),
        ("db_setup",    ["db_setup"]),
        ("extract",     ["extract"]),
        ("validations", ["validate"]),
        ("db_checks",   ["db_checks"]),
    ]
    for field_name, stage_names in _coverage:
        field_val = getattr(ctx.step, field_name, None)
        if field_val and not any(s in ctx.stages for s in stage_names):
            ctx.validate.passed = False
            errors.append(
                f"配置错误: step 提供了 {field_name}, 但所选 pipeline 未执行对应阶段"
            )

    passed: bool = ctx.validate.passed and ctx.db.checks_ok
    return StandardStepResult(
        name=ctx.step.name,
        passed=passed,
        request_sent=ctx.http.req_resolved,
        response=ctx.http.resp_data or None,
        extracted_vars=ctx.extract.extracted or None,
        errors=errors,
        operations=ctx.operations,
    )
