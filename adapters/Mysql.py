import types
import json
import datetime
import pymysql
import traceback
import decimal

from typing import Any
from pymysql import Connection

from utils.Logs import ExceptionLog
from dto.StandardDBTemplate import StandardDBConnectParamsStruct

class MysqlAdapter:
    def __init__(
        self,
        db_connect_params: StandardDBConnectParamsStruct,
    ) -> None:
        self._db_params: StandardDBConnectParamsStruct = db_connect_params
        # 设置默认连接超时时间和读写超时时间
        self._connect_timeout: int = 10
        self._read_timeout: int = 30
        self._write_timeout: int = 30

    @property
    def connection_info(self) -> dict: 
        tmp_data: dict = self._db_params.info
        tmp_data.setdefault("connect_timeout", self._connect_timeout)
        tmp_data.setdefault("read_timeout", self._read_timeout)
        tmp_data.setdefault("write_timeout", self._write_timeout)
        tmp_data.setdefault("charset", "utf8mb4")
        return tmp_data

    def test_connect(self) -> str: return "SELECT 1"

    def db_creator(self) -> types.ModuleType: return pymysql

    def _to_json_safe(self, val: Any) -> Any:
        """将非 JSON 可序列化类型转为 JSON 安全类型"""
        match val:
            case None: return None
            case datetime.datetime(): return val.isoformat()
            case datetime.date(): return val.isoformat()
            case datetime.timedelta(): return str(val)
            case decimal.Decimal(): return float(val)
            case set(): return list(val)
            case bytes(): return val.decode("utf-8", errors="replace")
            case _: return val
        return val

    def _rows_to_json_safe(self, rows: tuple[dict, ...] | list[dict]) -> list[dict]:
        """将查询结果逐行转为 JSON 可序列化的 list[dict]"""
        return [
            {k: self._to_json_safe(v) for k, v in row.items()}
            for row in rows
        ]

    def query(
        self,
        conn: Connection,
        sql: str,
        params: tuple | list | dict | None = None
    ) -> Any:
        ExceptionLog.info("开始执行sql查询...")
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                full_sql: str = cursor.mogrify(sql, params)
                ExceptionLog.info(f"执行的sql为: {full_sql}")
                cursor.execute(sql, params)
                res: tuple[dict, ...] = cursor.fetchall()
            ExceptionLog.info("查询成功, 共 %s 条记录", len(res))
            return self._rows_to_json_safe(res)
        except Exception as err:
            ExceptionLog.error(f"sql查询失败!!!,失败原因:{str(err)}\n错误堆栈: {traceback.format_exc()}")
            return []

    def set_connect_timeout(self, timeout: int) -> bool:
        if not timeout: return False
        self._connect_timeout = timeout
        ExceptionLog.info("重新设置设置数据库连接超时时间为 %s 秒", timeout)
        return True

    def set_read_timeout(self, timeout: int) -> bool:
        if not timeout: return False
        self._read_timeout = timeout
        ExceptionLog.info("重新设置数据库读取超时时间为 %s 秒", timeout)
        return True

    def set_write_timeout(self, timeout: int) -> bool:
        if not timeout: return False
        self._write_timeout = timeout
        ExceptionLog.info("重新设置数据库写入超时时间为 %s 秒", timeout)
        return True
