import types

from typing import Protocol, runtime_checkable, Any

@runtime_checkable
class StandardAdapterTrait(Protocol):
    '''
    标准适配器协议,所有要接入系统的适配器都必须满足这个协议
    '''
    @property
    def connection_info(self) -> dict: ... # 数据库的连接参数字典
    def test_connect(self) -> str: ... # 用于测试连接的 SQL 语句
    def db_creator(self) -> types.ModuleType: ... # 返回数据库的驱动模块，如 pymysql, psycopg2
    def query(
        self,
        conn: Any, # 这个参数是用于获取数据库连接游标对象
        sql: str,
        params: tuple | list | dict | None = None
    ) -> Any: ... # 查询语句,支持参数化查询,要处理None值
