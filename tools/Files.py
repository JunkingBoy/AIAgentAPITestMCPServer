import os
import json
import yaml
import shutil
import hashlib
import tempfile
import platform

from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from typing import Any, IO

'''
文件操作相关的工具方法统一存放
'''
def get_env_val(
    env_key: str,
) -> str:
    """
    读取环境变量
    """
    from utils.Logs import ExceptionLog
    if not env_key: return ""
    _env_name: str = os.getenv("APP_ENV", "dev")
    load_dotenv(dotenv_path=f".env.{_env_name}", override=False)
    try: return os.getenv(env_key.upper(), "")
    except Exception:
        ExceptionLog.error(f"获取环境变量{env_key.upper()}失败!")
        return ""

def create_dir(
    dir_name: str,
    need_date: bool = False
) -> str:
    '''
    创建指定名称目录,返回目录名称
    '''
    if not dir_name: raise ValueError('参数[dir_name]不能为空')
    try:
        cur_dir: Path = Path.cwd()
        # 当前目录下创建子文件夹
        dir_path: Path = cur_dir.joinpath(dir_name)
        if not need_date:
            dir_path.mkdir(parents=True, exist_ok=True)
            return dir_path.as_posix()
        else:
            today: str = datetime.now().strftime('%Y%m%d')
            tar_path: Path = dir_path.joinpath(today)
            if not tar_path.exists(): tar_path.mkdir(parents=True, exist_ok=True)
            return tar_path.as_posix()
    except Exception: raise Exception('创建目录失败')

def create_file(
    op_path: str,
    op_file_name: str,
    op_end_with: str,
    is_second: bool = False
) -> str:
    '''
    在指定路径下创建指定名称文件,返回文件名称
    '''
    if not op_path or not op_file_name or not op_end_with: raise ValueError('参数[op_path, op_file_name, op_end_with]不能为空')
    if not Path(op_path).exists() or not Path(op_path).is_dir(): raise ValueError('参数[op_path]指定的目录不存在或不是一个目录')
    try:
        if not is_second: tar_file: Path = Path(op_path).joinpath(f"{op_file_name}{op_end_with}")
        else:
            now: str = datetime.now().strftime("%H%M%S")
            tar_file: Path = Path(op_path).joinpath(f"{op_file_name}{now}{op_end_with}")
        if not tar_file.exists(): tar_file.touch()
        return tar_file.as_posix()
    except Exception: raise Exception('创建文件失败')

def del_path_or_file(path: str, only_file: bool = False) -> None:
    """
    删除指定路径（文件或目录）。
    
    :param path: 要删除的路径
    :param only_file: 若为 True，则只允许删除文件；若为 False，可删除文件或目录（包括非空目录）
    """
    if not path or not path.strip(): return
    real_path: Path = Path(path.strip())
    if not real_path.exists(): return
    if only_file:
        if not real_path.is_file(): return
        else: real_path.unlink()
    else:
        if real_path.is_file(): real_path.unlink()
        elif real_path.is_dir(): shutil.rmtree(real_path)
        else: real_path.unlink()

def calc_file_hash(content: bytes) -> str: return hashlib.sha256(content).hexdigest()

def search_download_file(
    base_path: str,
    filename: str
) -> str:
    """根据文件名中的日期信息在下载目录中查找文件,返回完整路径"""
    if not base_path or not filename: return ""
    try:
        target_day: str = filename[:8]
        date_dir: Path = Path.cwd().joinpath(base_path, target_day)
        if not date_dir.exists() or not date_dir.is_dir(): return ""
        for f in date_dir.iterdir():
            if f.is_file() and f.name.startswith(filename): return f.as_posix()
        return ""
    except Exception: return ""

if platform.system() == "Windows":
    import msvcrt
    def _lock(f: IO[Any]) -> None: msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
    def _unlock(f: IO[Any]) -> None: msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl
    def _lock(f: IO[Any]) -> None: fcntl.flock(f.fileno(), fcntl.LOCK_EX) # type: ignore
    def _unlock(f: IO[Any]) -> None: fcntl.flock(f.fileno(), fcntl.LOCK_UN) # type: ignore

class FileLock:
    def __init__(self, file: IO[Any]) -> None:
        self._file: IO[Any] = file
        self._pos: int = 0
    def __enter__(self) -> None:
        self._pos = self._file.tell()
        _lock(self._file)
    def __exit__(self, *args: Any) -> None:
        self._file.seek(self._pos)
        _unlock(self._file)

def atomic_write(file_path: str, content: dict) -> None:
    """将 dict 以 JSON 格式原子写入文件"""
    file: Path = Path(file_path)
    fd, tmp_path = tempfile.mkstemp(dir=file.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(content, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, file_path)
    except Exception:
        try: os.unlink(tmp_path)
        except OSError: pass
        raise

def get_yaml_content(file_path: str) -> dict:
    if not file_path: return {}
    _tmp_path: Path = Path(file_path)
    if not _tmp_path.exists(): return {}
    if not _tmp_path.is_file(): return {}
    if _tmp_path.suffix not in (".yaml", ".yml"): return {}
    else:
        with open(_tmp_path, "r", encoding="utf-8") as f: raw: dict = yaml.load(f, Loader=yaml.FullLoader)
        return raw
