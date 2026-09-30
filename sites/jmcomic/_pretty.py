"""兼容层: 仿 core/_pretty.py 的最简实现."""
from typing import Any

DOMAIN = "domain"
START = "start"
WARN = "warn"


def account_line(*args: Any, **kwargs: Any) -> str:
    """兼容多种签名: (idx,total,username,success,detail) 或 (idx,total,username,masked,status,msg)."""
    parts = [str(a) for a in args]
    parts += [f"{k}={v}" for k, v in kwargs.items()]
    return " ".join(parts)


def kv(key: str, label: str, value: str) -> str:
    return f"{key}={value}"


def title(name: str, ok: int, total: int) -> str:
    return f"{name} 成功 {ok}/{total}"