import os
import re
import json
import time

import yaml

from tools.Re import resolve_data
from utils.Pool import StandardRuntimeVariablePool
from tools.Files import get_yaml_content, get_env_val
from dto.StandardYAMLAnalysisTemplate import (
    StandardFlowMetaStruct,
    StandardStepRawStruct,
    StandardStepResult,
    StandardFlowResult,
)
from utils.Engine import parse_meta, parse_steps
from core.StandardStepPipeline import ensure_installed, run_step_pipeline
from dto.StandardStepPipelineTemplate import StepPipelineContext

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
    按 step.pipeline(或按是否含 request 推导)选择已注册的步骤组合。
    默认: http = db_setup → [HTTP → extract → validate] → db_checks; db = 纯 DB 步骤。
    无 request 时也可作为纯 DB 步骤(如先查库取数, 供后续步骤引用)。
    """
    ensure_installed()
    ctx: StepPipelineContext = StepPipelineContext(
        step=step,
        pool=pool,
        base_url=base_url,
        timeout=timeout,
    )
    name: str = step.pipeline or ("http" if step.request else "db")
    return await run_step_pipeline(name, ctx)
