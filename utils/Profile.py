from typing import Any

from utils.Logs import ExceptionLog
from tools.Files import get_yaml_content

_PROFILE_CONFIG_PATH: str = "config/profile.yml"
_PROFILES_CACHE: dict[str, Any] | None = None

def _load_profiles() -> dict[str, Any]:
    """
    加载 profile.yml，使用 get_yaml_content 读取。
    内部缓存，避免重复读文件。
    """
    global _PROFILES_CACHE
    if _PROFILES_CACHE is not None: return _PROFILES_CACHE

    raw: dict = get_yaml_content(_PROFILE_CONFIG_PATH)
    profiles: dict[str, Any] = raw.get("profiles", {}) if raw else {}
    if not profiles: ExceptionLog.error("profile.yml 配置为空或格式错误")
    _PROFILES_CACHE = profiles
    return profiles

def get_db_profile(profile: str) -> dict | None:
    profiles = _load_profiles()
    mapping: dict | None = profiles.get(profile)
    if mapping: return mapping
    else:
        ExceptionLog.error("未找到 profile 配置: %s", profile)
        return

def get_db_type_by_profile(profile: str) -> str | None:
    mapping = get_db_profile(profile)
    return mapping.get("db_type") if mapping else None

def get_system_by_profile(profile: str) -> str | None:
    mapping = get_db_profile(profile)
    return mapping.get("system") if mapping else None
