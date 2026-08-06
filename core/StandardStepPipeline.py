import time
import traceback

from typing import Callable, Awaitable

from utils.Logs import ExceptionLog
from dto.StandardStepPipelineTemplate import StepPipelineContext
from dto.StandardYAMLAnalysisTemplate import StandardStepResult

"""
StandardStepPipeline — step 级 pipeline 注册表 + 编排器

职责:
  register_step_pipeline     — 注册一个 step 组合(校验最后一步必须是 step_finalize)
  run_step_pipeline          — 查注册表 → 按序执行步骤 → 短路返回结果
  ensure_installed           — 幂等注册内置 step pipeline(所有入口共用)
"""

# step 步骤签名: async (ctx) -> StandardStepResult | None
StepHandler = Callable[[StepPipelineContext], Awaitable[StandardStepResult | None]]

_STEP_PIPELINES: dict[str, tuple[StepHandler, ...]] = {}
_INSTALLED: bool = False


def register_step_pipeline(name: str, steps: tuple[StepHandler, ...]) -> None:
    """注册一个 step 组合。校验最后一步必须是 step_finalize。"""
    from pipelines.StandardPublicStepPipelines import step_finalize
    if not steps:
        ExceptionLog.error(f"[Pipeline] 空步骤元组, 拒绝注册: {name}")
        return
    if steps[-1] is not step_finalize:
        ExceptionLog.error(
            f"[Pipeline] '{name}' 最后一步必须是 step_finalize, "
            f"实际为 {getattr(steps[-1], '__name__', steps[-1])} — 跳过注册"
        )
        return
    _STEP_PIPELINES[name] = steps
    ExceptionLog.info(f"[Pipeline] 已注册 step pipeline: name={name}, steps={len(steps)}")


async def run_step_pipeline(name: str, ctx: StepPipelineContext) -> StandardStepResult:
    """查注册表 → 按序执行步骤 → 非 None 即短路返回。"""
    steps: tuple[StepHandler, ...] | None = _STEP_PIPELINES.get(name)
    if not steps:
        raise LookupError(f"未注册的 step pipeline: {name}")

    for idx, step in enumerate(steps, start=1):
        step_name: str = getattr(step, "__name__", str(step))
        t0: float = time.time()
        try:
            result: StandardStepResult | None = await step(ctx)
            elapsed: float = round((time.time() - t0) * 1000, 1)
            if result is not None:
                ExceptionLog.info(
                    f"[Pipeline:{name}] 步骤{idx}/{len(steps)} [{step_name}] "
                    f"短路 | {elapsed}ms"
                )
                return result
            ExceptionLog.info(
                f"[Pipeline:{name}] 步骤{idx}/{len(steps)} [{step_name}] "
                f"通过 | {elapsed}ms"
            )
        except Exception as exc:
            elapsed = round((time.time() - t0) * 1000, 1)
            ExceptionLog.error(
                f"[Pipeline:{name}] 步骤{idx}/{len(steps)} [{step_name}] "
                f"异常: {str(exc)}\n{traceback.format_exc()} | {elapsed}ms"
            )
            return _fail_result(ctx, f"步骤 {step_name} 执行异常: {exc}")

    # 兜底: pipeline 未以 finalize 结束
    if ctx.result is not None: return ctx.result
    raise RuntimeError(f"[Pipeline:{name}] 执行完毕但无步骤返回结果, pipeline 必须以 step_finalize 结束")


def ensure_installed() -> None:
    """幂等注册内置 step pipeline。由 execute_step 入口调用一次。"""
    global _INSTALLED
    if _INSTALLED: return
    from pipelines.StandardHttpStepPipelines import install
    install()
    _INSTALLED = True


def _fail_result(ctx: StepPipelineContext, message: str) -> StandardStepResult:
    return StandardStepResult(name=ctx.step.name, passed=False, errors=[message])
