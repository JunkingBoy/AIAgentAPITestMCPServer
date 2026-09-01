import re
import uuid
import random
import string

from typing import Any
from datetime import datetime, timedelta


_PLACEHOLDER_RE: re.Pattern = re.compile(r"\$\{(.+?)\}")
_BUILTIN_RE: re.Pattern = re.compile(r"__(\w+)\(([^)]*)\)")

class _PlaceholderReplacer:
    """
    占位符替换器 — 工厂模式替代闭包，作为 re.sub 的回调。

    构造时将 pool 和 strict 收为内部状态，
    每次 match 调用 __call__ 执行单次替换。
    """
    def __init__(self, pool: Any, strict: bool) -> None:
        self._pool: Any = pool
        self._strict: bool = strict

    def __call__(self, m: re.Match) -> str:
        key: str = m.group(1)

        match key:
            case k if k.startswith("env."):
                # ${env.BASE_URL} → pool.get_env("BASE_URL")
                val: Any | None = self._pool.get_env(k.removeprefix("env."))
                if val is not None: return str(val)
            case k if k.startswith("__"):
                # ${__random(6)} → pool.call_builtins("__random(6)")
                val = self._pool.call_builtins(k)
                if val is not None: return str(val)
            case _:
                # ${access_token} → pool.get_runtime("access_token")
                val = self._pool.get_runtime(key)
                if val is not None: return val if isinstance(val, str) else str(val)
        # 未匹配
        if self._strict:
            raise ValueError(f"占位符 ${{{key}}} 在变量池中未找到")
        return m.group(0)  # 原样保留

def resolve_text(
    text: str,
    pool: Any,
    strict: bool = False,
) -> str:
    """
    扫描字符串中的 ${...} 占位符并从变量池取值替换。

    占位符三层路由（由函数解析前缀，不依赖 pool 内部逻辑）：
      ${env.XXX}    → pool.get_env("XXX")        环境变量层
      ${__func()}   → pool.call_builtin("__func") 内置函数层
      ${xxx}        → pool.get_runtime("xxx")     运行时变量层

    未匹配行为：
      strict=True  → 抛 ValueError
      strict=False → 原样保留 ${...}

    Args:
        text:   含占位符的原始字符串，如 "Bearer ${access_token}"
        pool:   变量池实例，需暴露 get_env / get_runtime / call_builtin 三个方法
        strict: 未匹配时是否抛异常，默认 False

    Returns:
        替换后的字符串，如 "Bearer eyJhbGciOiJIUzI1NiJ9"
    """
    if not text or "${" not in text: return text
    return _PLACEHOLDER_RE.sub(_PlaceholderReplacer(pool, strict), text)

def resolve_data(
    data: Any,
    pool: Any,
    strict: bool = False,
) -> Any:
    """
    递归遍历任意数据结构（str / dict / list），对所有 str 值执行 resolve_text。

    处理规则：
      str   → resolve_text 单值替换
      dict  → 递归替换所有 value
      list  → 递归替换所有元素
      其他  → 原样返回（int / float / bool / None）

    Args:
        data:   任意 Python 值
        pool:   变量池实例
        strict: 未匹配时是否抛异常

    Returns:
        替换后的数据结构，类型与入参一致
    """
    match data:
        case str(): return resolve_text(data, pool, strict)
        case dict(): return {k: resolve_data(v, pool, strict) for k, v in data.items()}
        case list(): return [resolve_data(item, pool, strict) for item in data]
        case _: return data

def builtin_random(raw_args: str = "") -> str:
      n: int = int(raw_args) if raw_args.isdigit() else 8
      return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def builtin_randint(raw_args: str = "") -> str:
    """
    纯数字随机整数（闭区间）:
      ${__randint()}              → [0, 9999999999]
      ${__randint(100)}           → [0, 100]
      ${__randint(1000000000,9999999999)} → [1000000000, 9999999999]
    返回 str，用于 number 型 JSON 字段或拼接手机号等纯数字场景。
    """
    parts: list[str] = [p.strip() for p in raw_args.split(",") if p.strip()]
    if not parts: return str(random.randint(0, 9_999_999_999))
    if len(parts) == 1: return str(random.randint(0, int(parts[0])))
    return str(random.randint(int(parts[0]), int(parts[1])))

def builtin_uuid() -> str: return str(uuid.uuid4()) # 36位uuid

def builtin_now(raw_args: str = "") -> str:
    """${__now()} → '2026-07-01 14:30:00'  或  ${__now(-1d)} → 昨天此时"""
    fmt: str = "%Y-%m-%d %H:%M:%S"
    base: datetime = datetime.now()
    if raw_args:
        offset: int = 0
        unit: str = "d"
        # 解析 "-1d" / "2h" / "30m" 等简单偏移
        m: re.Match | None = re.match(r"([+-]?\d+)([dhms])", raw_args)
        if m:
            offset = int(m.group(1))
            unit = m.group(2)
            match unit:
                case "d": base += timedelta(days=offset)
                case "h": base += timedelta(hours=offset)
                case "m": base += timedelta(minutes=offset)
                case "s": base += timedelta(seconds=offset)
    return base.strftime(fmt)
