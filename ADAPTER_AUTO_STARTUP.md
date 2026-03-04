## 应用启动自动启动 Adapters 说明

### 改动说明

在 [chat_guardian/api/app.py](chat_guardian/api/app.py) 中已添加应用生命周期管理功能，使得：

1. **应用启动时自动启动**：所有 `enabled_adapters` 中配置的 adapters 会在应用启动时自动启动
2. **应用关闭时自动停止**：所有 adapters 会在应用关闭时自动停止

### 工作流程

```python
# 应用启动时的流程：
1. FastAPI 应用初始化
2. 触发 lifespan startup 事件
3. 自动调用 container.adapter_manager.start_all()
4. 启动所有配置的 adapters
5. 应用开始接收请求

# 应用关闭时的流程：
1. 接收关闭信号
2. 触发 lifespan shutdown 事件
3. 自动调用 container.adapter_manager.stop_all()
4. 停止所有运行中的 adapters
5. 应用完全关闭
```

### 配置 Adapters

在 `.env` 文件中配置 `CHAT_GUARDIAN_ENABLED_ADAPTERS`：

```bash
# 启用 onebot 和 telegram adapters
CHAT_GUARDIAN_ENABLED_ADAPTERS=["onebot", "telegram"]

# 或在 Python 中配置
from chat_guardian.settings import settings
settings.enabled_adapters = ["onebot", "telegram"]
```

### 启动应用

```bash
# 方式 1：使用命令行
poetry run chat-guardian

# 方式 2：直接运行 Python
poetry run python -m chat_guardian.main

# 方式 3：使用 Uvicorn
poetry run uvicorn chat_guardian.api.app:create_app --host 0.0.0.0 --port 8000
```

应用启动时，日志中会显示：
```
🚀 应用启动，自动启动 adapters: ['onebot', 'telegram']
```

应用关闭时，日志中会显示：
```
🛑 应用关闭，停止所有 adapters
```

### 手动控制 Adapters（可选）

尽管 adapters 现在会自动启动/停止，您仍然可以通过 API 手动控制：

```bash
# 手动启动所有 adapters
curl -X POST http://localhost:8000/adapters/start

# 手动停止所有 adapters
curl -X POST http://localhost:8000/adapters/stop
```

### 测试

运行以下命令验证改动：

```bash
poetry run pytest tests/test_detection_engine.py tests/test_detection_triggers.py tests/test_rule_generation.py -q
```

当前所有测试通过：✅ 7 passed
