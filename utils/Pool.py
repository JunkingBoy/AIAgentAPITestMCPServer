import re
import traceback

from contextlib import contextmanager
from dbutils.pooled_db import PooledDB # 数据库连接池第三方库
from typing import Generator, TypeVar, Generic, Any, Callable

from tools.Re import _BUILTIN_RE
from utils.Logs import ExceptionLog
from trait.IStandardAdapter import StandardAdapterTrait
from tools.Re import (
    builtin_random,
    builtin_randint,
    builtin_uuid,
    builtin_now
)

T = TypeVar('T', bound=StandardAdapterTrait)
class StandardDatabasesConnectPool(Generic[T]):
    '''
    数据库连接池,只要适配器满足协议都可以创建对应的连接池
    '''
    def __init__(
        self,
        adapter: T,
    ) -> None:
        self._adapter: T = adapter
        self._pool: PooledDB = PooledDB(
            creator=self._adapter.db_creator(),
            maxconnections=10,
            mincached=2,
            maxcached=5,
            blocking=True,
            ping=1,
            **self._adapter.connection_info
        )

    @contextmanager
    def _connection(self) -> Generator[Any, None, None]:
        conn: Any = self._pool.connection()
        try: yield conn
        except Exception as err:
            ExceptionLog.error("获取数据库连接失败,异常原因: %s\n错误堆栈: %s", str(err), traceback.format_exc())
            ExceptionLog.info("获取数据库连接失败,失败原因: %s", str(err))
            if conn: conn.rollback()
            raise
        finally:
            if conn: conn.close()

    def test_conn(self) -> bool:
        ExceptionLog.info("测试数据库连接...")
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(self._adapter.test_connect())
                    if cursor.fetchone() is None:
                        ExceptionLog.info("测试数据库连接失败")
                        return False
                ExceptionLog.info("测试数据库连接成功")
                return True
        except Exception as err:
            ExceptionLog.error("测试数据库连接异常,异常原因: %s\n错误堆栈: %s", str(err), traceback.format_exc())
            ExceptionLog.error("测试数据库连接异常,异常原因: %s", str(err))
            return False

    def query(self, sql: str, params: tuple | list | dict | None = None) -> list:
        if not isinstance(params, (tuple, list, dict)): params = None
        try:
            with self._connection() as conn: return self._adapter.query(conn, sql, params)
        except Exception as err:
            ExceptionLog.error("数据库查询异常,异常原因: %s\n错误堆栈: %s", str(err), traceback.format_exc())
            ExceptionLog.error("数据库查询异常,执行sql: %s 失败", sql)
            return []

class StandardRuntimeVariablePool:
    '''
    一轮测试执行时的运行时变量池
    静态变量池 - _env
    动态变量池 - _runtime
    可调用函数 - _builtins
    '''
    def __init__(self) -> None:
        self._env: dict = {}
        self._runtime: dict = {}
        self._builtins: dict[str, Callable[..., str]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        self._builtins["random"] = builtin_random
        self._builtins["randint"] = builtin_randint
        self._builtins["uuid"] = builtin_uuid
        self._builtins["now"] = builtin_now

    @property
    def info(self) -> dict:
        return {
            "env": dict(self._env),
            "runtime": dict(self._runtime),
            "builtins": list(self._builtins)
        }

    # 静态内存
    def set_env(self, k: str, v: str) -> None: self._env[k.upper()] = v
    def get_env(self, k: str) -> str | None: return self._env.get(k.upper())
    def load_from_dict(self, data: dict) -> None:
        for k, v in data.items(): self._env[k.upper()] = v

    # 运行时内存
    def set_runtime(self, k: str, v: Any) -> None: self._runtime[k.upper()] = v
    def get_runtime(self, k: str) -> Any | None: return self._runtime.get(k.upper())
    def preload_variables(self, variables: dict) -> None:
        for k, v in variables.items():
            if not k.startswith("_"): self._runtime[k.upper()] = v

    # 提供的内置函数
    def call_builtins(self, k: str) -> str | None:
        """
        被 _PlaceholderReplacer 调用。
        key 格式: "__random(6)" 或 "__uuid()"
        解析函数名 + 参数 → 调用对应函数 → 返回 str
        """
        m: re.Match | None = _BUILTIN_RE.fullmatch(k)
        if not m:
            ExceptionLog.info("内置函数调用失败,函数名: %s", k)
            return

        # 获取函数和参数
        func_name: str = m.group(1)
        kwargs: str = m.group(2)

        func: Callable[..., str] | None = self._builtins.get(func_name)
        if not func: return
        if kwargs.strip(): return func(kwargs.strip())
        else: return func()
