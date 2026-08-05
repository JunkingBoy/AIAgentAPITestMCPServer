import sys
import logging

from tools.Files import create_dir

def setup_alembic_logger() -> None:
    """配置 alembic 日志：输出到控制台，不影响其他 logger"""
    logger = logging.getLogger("alembic")
    if logger.handlers: return # 防止重复添加
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(levelname)-5.5s [%(name)s] %(message)s")
    )
    logger.addHandler(handler)

def _configure_logger() -> logging.Logger:
    """配置并返回 ExceptionLog logger（模块加载时执行一次）。"""
    logger = logging.getLogger("ExceptionLog")

    # 防止重复配置（模块重加载场景）
    if logger.handlers: return logger
    logger.setLevel(logging.DEBUG)
    err_log = create_dir("logs/err")
    info_log = create_dir("logs/info")
    if not err_log or not info_log: raise RuntimeError("日志目录创建失败")

    # 错误日志文件处理器
    err_handler = logging.FileHandler(
        f"{err_log}/err.log",
        encoding="utf-8-sig",
        mode="a",
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s:%(pathname)s:%(name)s:%(levelname)s:%(message)s"
        )
    )
    logger.addHandler(err_handler)

    # 运行日志文件处理器
    info_handler = logging.FileHandler(
        f"{info_log}/run.log",
        encoding="utf-8-sig",
        mode="a",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(
        logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    )
    logger.addHandler(info_handler)

    return logger

# 模块级实例 —— Python 模块天然单例，一次导入全局复用
ExceptionLog: logging.Logger = _configure_logger()
