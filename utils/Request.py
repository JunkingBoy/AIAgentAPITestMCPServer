import httpx
import traceback

from typing import Any

from utils.Logs import ExceptionLog
from dto.StandardHttpTemplate import StandardReqYAMLSetStruct
from dto.StandardLayerResponseTemplate import StandardLayerStructTemplate

async def req_meta(
    data: StandardReqYAMLSetStruct,
    base_url: str = "",
    timeout: float = 15.0,
) -> StandardLayerStructTemplate[dict]:
    """
    发送 HTTP 请求并返回结构化响应。
    自动从 data 中推断请求体格式：
    """
    if not data.path: url = base_url
    else:
        base = base_url.rstrip("/")
        path = data.path.lstrip("/")
        url = f"{base}/{path}" if base else path

    req_kwargs: dict[str, Any] = {}

    if data.params: req_kwargs["params"] = data.params
    if data.headers: req_kwargs["headers"] = data.headers

    # 请求体：form 优先于 body
    if data.form: req_kwargs["data"] = data.form
    elif data.body: req_kwargs["json"] = data.body

    # SSL 验证（None → 使用 httpx 默认 True）
    verify: bool = data.ssl if data.ssl is not None else True

    # ── 发送请求 ──────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(
            verify=verify,
            timeout=httpx.Timeout(timeout),
        ) as client:
            resp = await client.request(
                method=data.method or "GET",
                url=url,
                **req_kwargs,
            )
    except httpx.TimeoutException as exc:
        ExceptionLog.error(
            "请求超时! 超时原因: %s, 堆栈信息: %s",
            str(exc),
            traceback.format_exc(),
        )
        ExceptionLog.info("请求 %s 超时!", url)
        return StandardLayerStructTemplate.ok(
            data={
                "url": url,
                "status_code": None,
                "headers": None,
                "body": str(exc),
                "elapsed": None,
            }
        )
    except httpx.HTTPStatusError as exc:
        # 4xx/5xx —— 响应本身是完整的，只是状态码异常，不视为 error
        return StandardLayerStructTemplate.ok(
            data=_parse_response(exc.response),
        )
    except httpx.RequestError as exc:
        ExceptionLog.error(
            "请求错误: %s, 堆栈信息: %s",
            str(exc),
            traceback.format_exc(),
        )
        ExceptionLog.error("请求 %s 出错!", url)
        return StandardLayerStructTemplate.error(message=str(exc))
    except Exception as exc:
        ExceptionLog.error(
            "未知错误: %s, 堆栈信息: %s",
            str(exc),
            traceback.format_exc(),
        )
        ExceptionLog.error("请求 %s 发生未知错误!", url)
        return StandardLayerStructTemplate.error(message=str(exc))
    return StandardLayerStructTemplate.ok(data=_parse_response(resp))

def _parse_response(resp: httpx.Response) -> dict:
    """将 httpx.Response 转为统一的结果字典。"""
    try: body: Any = resp.json()
    except Exception: body = resp.text
    return {
        "url": str(resp.url),
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": body,
        "elapsed": resp.elapsed.total_seconds(),
    }
