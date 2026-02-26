"""程序入口模块。

提供 `run()` 函数用于在本地通过 Uvicorn 启动应用。
"""

from chat_guardian.api.app import create_app


def run() -> None:
    """通过 Uvicorn 启动 FastAPI 应用。

    仅在作为脚本或容器入口时调用。
    """
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
