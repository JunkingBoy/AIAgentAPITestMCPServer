import types
import decimal
import oracledb
import datetime
import traceback

from typing import Any, cast

from utils.Logs import ExceptionLog
from dto.StandardDBTemplate import StandardDBConnectParamsStruct

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
