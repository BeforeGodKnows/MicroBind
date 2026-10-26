"""The deployment switch is independent of the per-job smart-review choice."""

import os


def enabled():
    return os.getenv("MICROBIND_LLM_ENABLED", "0") == "1"


def require_enabled():
    if not enabled():
        raise ValueError("模型功能已关闭；请设置 MICROBIND_LLM_ENABLED=1，并重新创建相关容器")
