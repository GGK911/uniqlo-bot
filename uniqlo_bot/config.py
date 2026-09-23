"""配置加载。"""
import os

import yaml

# 默认配置，用户 config.yaml 未填的字段回退到这里
DEFAULT = {
    "uniqlo": {
        "base_url": "https://www.uniqlo.cn",
        "index_path": "/wechat/config_1/zh_CN/cms-wechat-config.json",
        "image_base": "https://www.uniqlo.cn/hmall/test",
        "pages": [
            {"route": "/wechat/timelimit", "name": "限时特优"},
            {"route": "/wechat/super-u", "name": "超值精选"},
        ],
        "request": {"timeout": 20, "retries": 3, "delay": 0.3},
    },
    "filter": {"min_discount_rate": 0, "only_in_stock": True},
    "storage": {"db_path": "data/uniqlo.db"},
    "image_cache": {"dir": "data/images", "concurrency": 4},
    "schedule": {"enabled": True, "times": ["09:00", "15:00"], "stale_hours": 24},
    "wechat": {"enabled": False, "webhook_url": "", "top_n": 10},
    "web": {"host": "0.0.0.0", "port": 8000},
}


def _merge(base, override):
    """递归合并：override 中非空的键覆盖 base。"""
    if not isinstance(override, dict):
        return override if override is not None else base
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


def load_config(path="config.yaml"):
    """加载配置文件；文件不存在时回退默认值。"""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
    else:
        user_cfg = {}
    return _merge(DEFAULT, user_cfg)
