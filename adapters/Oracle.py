import types
import decimal
import oracledb
import datetime
import traceback

from typing import Any, cast

from utils.Logs import ExceptionLog
from tools.Files import get_env_val
from dto.StandardDBTemplate import StandardDBConnectParamsStruct

def is_thick_mode_enabled() -> bool:
    """读取 ORACLE_THICK_MODE_ENABLED 开关, 判断是否启用 thick 模式。
    开启值: true/1/on/yes(大小写不敏感); 缺字段或其它值 → False(thin)。"""
    val: str = get_env_val("ORACLE_THICK_MODE_ENABLED")
    if not val: return False
    return val.strip().lower() in ("true", "1", "yes", "on")

def ensure_oracle_client() -> None:
    """进程内启用 oracledb thick 模式(幂等, 应在首次 oracledb 连接前调用)。
    仅当开关开启且配置了 ORACLE_CLIENT_LIB_DIR 时生效;
    未开启 / 未配置路径 / 初始化失败 → 保持 thin 模式并记录日志。"""
    if not oracledb.is_thin_mode(): return  # 已是 thick 模式
    if not is_thick_mode_enabled():
        ExceptionLog.info("[Oracle] ORACLE_THICK_MODE_ENABLED 未开启, 使用 thin 模式")
        return
    lib_dir: str = get_env_val("ORACLE_CLIENT_LIB_DIR")
    if not lib_dir:
        ExceptionLog.error(
            "[Oracle] 已开启 thick 模式但未配置 ORACLE_CLIENT_LIB_DIR, 回退 thin 模式"
        )
        return
    try:
        oracledb.init_oracle_client(lib_dir=lib_dir)
        ExceptionLog.info("[Oracle] thick 模式已启用, lib_dir=%s", lib_dir)
    except Exception as exc:
        ExceptionLog.error(
            "[Oracle] 初始化 Oracle Client 失败, 回退 thin 模式: %s", exc
        )

def oracle_error_hint(exc: Exception) -> str:
    """将 oracledb 驱动异常转成可操作的提示信息, 供调用方写入日志。"""
    text: str = str(exc)
    if "DPY-3010" in text:
        return (
            "Oracle 连接失败: 该 Oracle 版本过老(thin 模式仅支持 12.1+), "
            "请在 .env.dev 配置 ORACLE_THICK_MODE_ENABLED=true 和 "
            "ORACLE_CLIENT_LIB_DIR 以启用 thick 模式"
        )
    return f"Oracle 连接失败: {text}"

class OracleAdapter:
    def __init__(
        self,
        db_connect_params: StandardDBConnectParamsStruct,
    ) -> None:
        self._db_params: StandardDBConnectParamsStruct = db_connect_params
        self._connect_timeout: int = 10
        self._read_timeout: int = 30

    @property
    def connection_info(self) -> dict:
        _service_name: str = self._db_params.database or ""
        dsn: str = oracledb.makedsn(
            self._db_params.host,
            self._db_params.port,
            service_name=_service_name,
        )
        return {
            "user": self._db_params.user,
            "password": self._db_params.password,
            "dsn": dsn,
        }

    def test_connect(self) -> str: return "SELECT 1 FROM DUAL"

    def db_creator(self) -> types.ModuleType: return oracledb

    def _to_json_safe(self, val: Any) -> Any:
        """将非 JSON 可序列化类型转为 JSON 安全类型"""
        match val:
            case None: return None
            case oracledb.LOB(): return val.read()
            case datetime.datetime(): return val.isoformat()
            case datetime.date(): return val.isoformat()
            case datetime.timedelta(): return str(val)
            case decimal.Decimal(): return float(val)
            case set(): return list(val)
            case bytes(): return val.decode("utf-8", errors="replace")
            case _: return val

    def _rows_to_json_safe(self, rows: list[dict]) -> list[dict]:
        return [
            {k: self._to_json_safe(v) for k, v in row.items()}
            for row in rows
        ]

    def query(
        self,
        conn: oracledb.Connection,
        sql: str,
        params: tuple | list | dict | None = None
    ) -> list[dict]:
        ExceptionLog.info("开始执行 Oracle 查询...")
        try:
            # oracledb 使用 :name 命名参数风格（如 :enabled, :is_stop_used），无 mogrify 方法
            ExceptionLog.info(f"执行的sql为: {sql}")
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                columns: list[str] = [cast(str, col[0]) for col in (cursor.description or [])]
                rows_raw: list[tuple] = cursor.fetchall()
                res: list[dict] = [dict(zip(columns, row)) for row in rows_raw]
            ExceptionLog.info("查询成功, 共 %s 条记录", len(res))
            return self._rows_to_json_safe(res)
        except Exception as err:
            ExceptionLog.error(
                f"Oracle 查询失败!!!,失败原因:{str(err)}\n错误堆栈: {traceback.format_exc()}"
            )
            ExceptionLog.error("%s", oracle_error_hint(err))
            return []

    def set_connect_timeout(self, timeout: int) -> bool:
        if not timeout:
            return False
        self._connect_timeout = timeout
        ExceptionLog.info("重新设置数据库连接超时时间为 %s 秒", timeout)
        return True

    def set_read_timeout(self, timeout: int) -> bool:
        if not timeout:
            return False
        self._read_timeout = timeout
        ExceptionLog.info("重新设置数据库读取超时时间为 %s 秒", timeout)
        return True
