import os
import re
import json
import time

import yaml

from typing import Any

from tools.Re import resolve_data
from utils.Request import req_meta
from utils.Pool import StandardRuntimeVariablePool
from utils.Executor import exec_step as exec_db_step
from tools.Files import get_yaml_content, get_env_val
from dto.StandardDBTemplate import StandardDBStepStruct
from dto.StandardHttpTemplate import StandardReqYAMLSetStruct
from dto.StandardLayerResponseTemplate import StandardLayerStructTemplate
from dto.StandardYAMLAnalysisTemplate import (
    StandardFlowMetaStruct,
    StandardStepRawStruct,
    StandardStepResult,
    StandardFlowResult,
)
from utils.Engine import parse_meta, parse_steps, jsonpath_get

def _load_env_to_pool(yaml_path: str, pool: StandardRuntimeVariablePool) -> None:
    """扫描 YAML 中所有 ${env.XXX} 引用，加载到变量池"""
    raw: dict = get_yaml_content(yaml_path)
    raw_json: str = json.dumps(raw)
    env_refs: set[str] = set(re.findall(r"\$\{env\.(\w+)\}", raw_json))

    for key in env_refs:
        val: str = get_env_val(key)
        if val: pool.set_env(key, val)

async def _run_from_dict(
    raw: dict,
    pool: StandardRuntimeVariablePool | None = None,
    fail_fast: bool = True,
) -> StandardFlowResult:
    """从已解析的 YAML dict 执行完整流程（内部核心）"""
    start: float = time.time()
    pool = pool or StandardRuntimeVariablePool()

    # 1. 第一轮 resolve（替换 ${env.XXX}）
    resolved: dict = resolve_data(raw, pool)

    # 2. 解析为 struct
    meta: StandardFlowMetaStruct = parse_meta(resolved)
    pool.preload_variables(meta.variables)

    steps: list[StandardStepRawStruct] = parse_steps(resolved)
    timeout: float = float(meta.timeout) if meta.timeout else 15.0

    # 3. 逐个执行 step
    step_results: list[StandardStepResult] = []
    for step in steps:
        result: StandardStepResult = await execute_step(step, pool, meta.base_url, timeout)
        step_results.append(result)
        if not result.passed and fail_fast: break

    # 4. 聚合报告
    duration: float = time.time() - start
    passed_count: int = sum(1 for s in step_results if s.passed)
    failed_count: int = sum(1 for s in step_results if not s.passed)
    return StandardFlowResult(
        flow_name=meta.name,
        total=len(step_results),
        passed=passed_count,
        failed=failed_count,
        steps=step_results,
        duration=duration,
    )

async def run(
    yaml_path: str,
    fail_fast: bool = True,
) -> StandardFlowResult:
    """执行完整业务流程（文件入口）"""
    raw: dict = get_yaml_content(yaml_path)
    pool: StandardRuntimeVariablePool = StandardRuntimeVariablePool()
    _load_env_to_pool(yaml_path, pool)
    return await _run_from_dict(raw, pool, fail_fast)

async def run_yaml_test(
    yaml_content: str,
    fail_fast: bool = True,
    env: str | None = None,
    variables: dict | None = None,
) -> StandardFlowResult:
    """
    MCP 入口：执行 YAML API 测试流程。
    AI 可直接传入 YAML 内容，无需写文件。
    """
    if env: os.environ.setdefault("APP_ENV", env)
    raw: dict = yaml.safe_load(yaml_content)
    pool: StandardRuntimeVariablePool = StandardRuntimeVariablePool()
    if variables:
        for k, v in variables.items(): pool.set_runtime(k, v)
    return await _run_from_dict(raw, pool, fail_fast)

async def execute_step(
    step: StandardStepRawStruct,
    pool: StandardRuntimeVariablePool,
    base_url: str,
    timeout: float,
) -> StandardStepResult:
    """
    执行单个 step。
    流程: resolve → db_setup(inject) → HTTP → extract → validate
    """
    errors: list[str] = []
    extracted: dict[str, Any] = {}

    # ── resolve 运行时占位符 ─────────────────────────────
    if not step.request: return StandardStepResult(name=step.name, passed=True)

    req_dict: dict = step.request.model_dump()
    req_resolved: dict = resolve_data(req_dict, pool)

    # ── db_setup ──────────────────────────────────────────
    if step.db_setup:
        for ds_dict in step.db_setup:
            ds_resolved: dict = resolve_data(ds_dict, pool)
            ds_struct: StandardDBStepStruct = StandardDBStepStruct.from_dict(ds_resolved)
            ds_result: StandardLayerStructTemplate = exec_db_step(ds_struct)
            if ds_result.is_error:
                return StandardStepResult(
                    name=step.name,
                    passed=False,
                    errors=[f"db_setup 失败: {ds_result.message}"],
                )

    # ── HTTP 请求 ────────────────────────────────────────
    try:
        req_struct: StandardReqYAMLSetStruct = StandardReqYAMLSetStruct.from_dict(req_resolved)
        result: StandardLayerStructTemplate = await req_meta(
            data=req_struct, base_url=base_url, timeout=timeout
        )
    except Exception as exc:
        return StandardStepResult(
            name=step.name,
            passed=False,
            errors=[f"请求异常: {exc}"],
        )

    if result.is_error:
        return StandardStepResult(
            name=step.name,
            passed=False,
            errors=[result.message or "请求失败"],
        )

    resp_data: dict = result.data or {}
    status_code: int | None = resp_data.get("status_code")
    resp_body: Any = resp_data.get("body", {})

    # ── extract ──────────────────────────────────────────
    resp_json: Any = resp_body if isinstance(resp_body, dict) else {}
    if step.extract:
        for var_name, jsonpath_expr in step.extract.items():
            value: Any = jsonpath_get(resp_json, jsonpath_expr)
            if value is not None:
                pool.set_runtime(var_name, value)
                extracted[var_name] = value

    # ── validate ─────────────────────────────────────────
    all_passed: bool = True
    if step.validations:
        for v in step.validations:
            check: str = v.get("check", "")
            assert_type: str = v.get("assert", "equals")
            expected: Any = v.get("value")

            if check == "status_code":
                if status_code != expected:
                    all_passed = False
                    errors.append(
                        f"状态码断言失败: 期望 {expected}, 实际 {status_code}"
                    )

            elif check.startswith("$."):
                actual: Any = jsonpath_get(resp_json, check)
                # 目前只支持 equals
                if actual != expected:
                    all_passed = False
                    errors.append(
                        f"{check} 断言失败: 期望 {expected}, 实际 {actual}"
                    )

    # ── db_checks ─────────────────────────────────────────
    if step.db_checks:
        for dc_dict in step.db_checks:
            dc_dict.setdefault("action", "SELECT")
            dc_resolved: dict = resolve_data(dc_dict, pool)
            dc_struct: StandardDBStepStruct = StandardDBStepStruct.from_dict(dc_resolved)
            dc_result: StandardLayerStructTemplate = exec_db_step(dc_struct)

            if dc_result.is_error:
                all_passed = False
                errors.append(f"db_checks 查询失败: {dc_result.message}")
            elif dc_struct.expected is not None:
                rows: list[dict] = dc_result.data or []
                if dc_struct.expected and not rows:
                    all_passed = False
                    errors.append(f"db_checks 预期有数据, 但 {dc_struct.table} 查询无结果")
                elif not dc_struct.expected and rows:
                    all_passed = False
                    errors.append(
                        f"db_checks 预期无数据, 但 {dc_struct.table} 返回 {len(rows)} 条"
                    )

    return StandardStepResult(
        name=step.name,
        passed=all_passed,
        request_sent=req_resolved,
        response=resp_data,
        extracted_vars=extracted or None,
        errors=errors,
    )
