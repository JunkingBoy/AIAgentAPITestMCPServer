from typing import Any
from dataclasses import dataclass, field

from utils.Pool import StandardRuntimeVariablePool
from dto.StandardYAMLAnalysisTemplate import StandardStepRawStruct, StandardStepResult

@dataclass
class DBIOStepContext:
    """db_setup 与 db_checks 的 I/O 结果 — step_db_setup / step_db_checks 写入, step_finalize 消费"""
    setup_ok: bool = True
    setup_error: str | None = None
    checks_ok: bool = True
    check_errors: list[str] = field(default_factory=list)

@dataclass
class HTTPStepContext:
    """HTTP 请求 I/O — step_send_request 写入, step_extract / step_validate / step_finalize 消费"""
    req_resolved: dict | None = None
    resp_data: dict = field(default_factory=dict)
    status_code: int | None = None
    resp_json: Any = field(default_factory=dict)

@dataclass
class ExtractStepContext:
    """extract 结果(已注入 pool 的变量)— step_db_setup / step_extract 写入, step_finalize 消费"""
    extracted: dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidateStepContext:
    """校验结果 — step_validate 写入, step_finalize 消费"""
    errors: list[str] = field(default_factory=list)
    passed: bool = True

@dataclass
class StepPipelineContext:
    """step 级 pipeline 共享上下文 — 组合 session / db / http / extract / validate 五个子结构"""
    step: StandardStepRawStruct              # 原始 step 定义(输入)
    pool: StandardRuntimeVariablePool        # 运行时变量池(输入, 各步骤读写)
    base_url: str = ""                       # 请求基址(输入)
    timeout: float = 15.0                    # 请求超时(输入)
    db: DBIOStepContext = field(default_factory=DBIOStepContext)
    http: HTTPStepContext = field(default_factory=HTTPStepContext)
    extract: ExtractStepContext = field(default_factory=ExtractStepContext)
    validate: ValidateStepContext = field(default_factory=ValidateStepContext)
    stages: set[str] = field(default_factory=set)          # 已执行阶段标记(finalize 做覆盖校验)
    result: StandardStepResult | None = None                # 非 None = 短路信号
