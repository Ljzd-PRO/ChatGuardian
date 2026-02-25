"""程序入口模块。

提供 `run()` 函数用于在本地通过 Uvicorn 启动应用。
"""

from loguru import logger
logger.add("chat_guardian.log", rotation="10 MB", retention="7 days", encoding="utf-8", enqueue=True, level="DEBUG")

from chat_guardian.api.app import create_app


def run() -> None:
    """通过 Uvicorn 启动 FastAPI 应用。

    仅在作为脚本或容器入口时调用。
    """
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
