import copy
import traceback
import threading

from typing import Callable, Any
from pydantic import BaseModel, ConfigDict

from tools.Files import get_env_val
from utils.Logs import ExceptionLog
from adapters.Mysql import MysqlAdapter
from adapters.Oracle import OracleAdapter, ensure_oracle_client, oracle_error_hint
from utils.Pool import StandardDatabasesConnectPool
from trait.IStandardAdapter import StandardAdapterTrait
from dto.StandardDBTemplate import StandardDBConnectParamsStruct

class PoolRegistry(BaseModel):
    """
    数据库连接池注册表（全局共享 struct 容器）
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lock: threading.Lock = threading.Lock()
    adapters: dict[str, Callable[..., Any]] = {}
    sql_pools: dict[str, StandardDatabasesConnectPool] = {}

_POOL_REGISTRY: PoolRegistry = PoolRegistry()

class StandardDatabasesConnPoolFactory:
    '''
    关系型数据库和非关系型数据库连接池容器工厂
    所有的数据库连接池容器都需要从这里使用
    '''
    def __init__(
        self,
    ) -> None:
        if hasattr(self, '_initialized') and self._initialized: return
        self._initialized: bool = True
        self._register_default_adapter()
        # 在首次 oracledb 连接前尽早确定进程级 thick/thin 模式
        ensure_oracle_client()

    @property
    def sql_pools(self) -> dict: return copy.deepcopy(_POOL_REGISTRY.sql_pools)

    def _register_default_adapter(self) -> None:
        with _POOL_REGISTRY.lock:
            _POOL_REGISTRY.adapters.setdefault("mysql", MysqlAdapter)
            _POOL_REGISTRY.adapters.setdefault("oracle", OracleAdapter)

    def _load_config(
        self,
        sys: str,
        db_typ: str
    ) -> StandardDBConnectParamsStruct | None:
        '''
        加载数据库配置函数,
        目前默认会从.env文件中加载数据库配置,后期支持拓展
        '''
        if not sys or not db_typ:
            ExceptionLog.info("获取数据库配置失败，请检查系统名称和数据库类型是否正确!系统名称: %s,数据库类型: %s", sys, db_typ)
            return
        if db_typ not in _POOL_REGISTRY.adapters:
            ExceptionLog.info("获取数据库配置失败，数据库类型未注册: %s", db_typ)
            return
        _host: str = get_env_val(f"{sys}_{db_typ}_host")
        _port_str: str = get_env_val(f"{sys}_{db_typ}_port")
        _username: str = get_env_val(f"{sys}_{db_typ}_user")
        _password: str = get_env_val(f"{sys}_{db_typ}_password")
        _database: str = get_env_val(f"{sys}_{db_typ}_database")
        try:
            _port: int = int(_port_str)
        except Exception as err:
            ExceptionLog.error("端口转换失败,异常原因: %s\n错误堆栈: %s", str(err), traceback.format_exc())
            ExceptionLog.error("端口转换失败!端口为: %s", _port_str)
            return
        _tmp_data: dict = {}
        _tmp_data.setdefault("host", _host)
        _tmp_data.setdefault("port", _port)
        _tmp_data.setdefault("user", _username)
        _tmp_data.setdefault("password", _password)
        _tmp_data.setdefault("database", _database)
        ExceptionLog.info("数据库配置数据组装完成. 数据为: %s", _tmp_data)
        return StandardDBConnectParamsStruct(**_tmp_data)

    def get_pool(
        self,
        sys: str,
        db_typ: str,
        env: str
    ) -> StandardDatabasesConnectPool | None:
        config: StandardDBConnectParamsStruct | None = self._load_config(sys, db_typ)
        if config is None:
            ExceptionLog.info("获取数据库连接池失败，请检查系统名称和数据库类型是否正确!,系统名称: %s, 数据库类型: %s", sys, db_typ)
            return
        else:
            ada_cls: Callable[..., Any] | None = _POOL_REGISTRY.adapters.get(db_typ)
            if ada_cls is None:
                ExceptionLog.info("获取数据库连接池失败，数据库类型未注册: %s", db_typ)
                return
            tmp_pool_key: str = f"{sys}_{db_typ}_{env}".upper()
            if tmp_pool_key in _POOL_REGISTRY.sql_pools: return _POOL_REGISTRY.sql_pools.get(tmp_pool_key)
            with _POOL_REGISTRY.lock:
                if tmp_pool_key in _POOL_REGISTRY.sql_pools: return _POOL_REGISTRY.sql_pools.get(tmp_pool_key)
                try:
                    adapter: StandardAdapterTrait = ada_cls(config)
                    pool: StandardDatabasesConnectPool = StandardDatabasesConnectPool(adapter)
                    _POOL_REGISTRY.sql_pools.setdefault(tmp_pool_key, pool)
                    ExceptionLog.info("获取数据库连接池成功!")
                    return pool
                except Exception as err:
                    ExceptionLog.error("获取数据库连接池失败,异常原因: %s\n错误堆栈: %s", str(err), traceback.format_exc())
                    if db_typ == "oracle": ExceptionLog.error("%s", oracle_error_hint(err))
                    else: ExceptionLog.error("获取数据库连接池失败,请检查系统名称和数据库类型是否正确!")
                    return
