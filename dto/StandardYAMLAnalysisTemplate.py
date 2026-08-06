import copy
import json

from typing import Any
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, ConfigDict

from dto.StandardHttpTemplate import StandardReqYAMLSetStruct

class StandardFlowMetaStruct(BaseModel):
    """
    YAML 文件头元信息
    """
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    base_url: str
    timeout: str | None = None               # str，因为 ${env.XXX} 解析前是字符串
    variables: dict[str, Any] = {}           # 全局变量（YAML 锚点）

class StandardStepRawStruct(BaseModel):
    """
    对应 YAML 中一个 step 条目
    """
    model_config = ConfigDict(from_attributes=True)

    name: str
    pipeline: str | None = None            # 可选: 指定 step 级 pipeline 组合, 缺省按 request 是否为空推导
    request: StandardReqYAMLSetStruct | None = None
    db_setup: list[dict] | None = None
    db_checks: list[dict] | None = None
    extract: dict[str, str] | None = None
    validations: list[dict] | None = None

@dataclass
class StandardStepResult:
    name: str
    passed: bool
    request_sent: dict | None = None
    response: dict | None = None
    extracted_vars: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    operations: list[dict] = field(default_factory=list)   # 报告专用: 逐步操作痕迹, 控制台 JSON 不展示

    @property
    def info(self) -> dict:
        info: dict = copy.deepcopy(self.__dict__)
        info.pop("operations", None)   # 报告专用字段, 从控制台输出排除
        return info

@dataclass
class StandardFlowResult:
    flow_name: str
    total: int
    passed: int
    failed: int
    steps: list[StandardStepResult]
    duration: float

    @property
    def is_passed(self) -> bool: return self.failed == 0
    @property
    def info_str(self) -> str: return json.dumps(self._info(), ensure_ascii=False, indent=2)
    @property
    def info(self) -> dict: return copy.deepcopy(self._info())

    def _info(self) -> dict:
        steps_info: list[dict] = []
        for s in self.steps:
            d: dict = asdict(s)
            d.pop("operations", None)   # 报告专用字段, 从控制台输出排除
            steps_info.append(d)
        return {
            "flow_name": self.flow_name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "is_passed": self.is_passed,
            "duration": round(self.duration, 3),
            "steps": steps_info,
        }
