"""兼容层: 仿 core/ql_notify.py 的最简实现 (无推送通道时静默成功)."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def send_sync(*args: Any, **kwargs: Any) -> None:
    """send_sync 占位: 在青龙面板里 SEND_HOOK 等环境变量未配置时静默."""
    logger.debug("send_sync noop: %s", args)