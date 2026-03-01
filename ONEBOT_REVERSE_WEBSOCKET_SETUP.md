# OneBot 反向 WebSocket 连接配置指南

## 概述

ChatGuardian 的 OneBot 适配器现已改为使用**反向 WebSocket 连接方式**，作为 WebSocket 服务端让 OneBot 实例连接。

### 工作流程

```
OneBot 实例 (客户端)  →  WebSocket 连接  →  ChatGuardian (服务端)
                        ws://host:port/ws/event/
```

## 配置步骤

### 1. 配置 ChatGuardian 环境变量

在 `.env` 文件中添加或修改以下配置：

```env
# OneBot 反向 WebSocket 入站
CHAT_GUARDIAN_ONEBOT_HOST=0.0.0.0
CHAT_GUARDIAN_ONEBOT_PORT=8081
CHAT_GUARDIAN_ONEBOT_ACCESS_TOKEN=your_secret_token

# 启用 OneBot 适配器
CHAT_GUARDIAN_ENABLED_ADAPTERS=onebot
```

**参数说明：**
- `CHAT_GUARDIAN_ONEBOT_HOST`：WebSocket 服务器监听地址（默认：`127.0.0.1`）
  - `127.0.0.1`：仅本地访问
  - `0.0.0.0`：接受所有网络接口上的连接
- `CHAT_GUARDIAN_ONEBOT_PORT`：WebSocket 服务器监听端口（默认：`8081`）
- `CHAT_GUARDIAN_ONEBOT_ACCESS_TOKEN`：可选的访问令牌，用于身份验证

### 2. 配置 OneBot 实例

根据你使用的 OneBot 实现，配置反向 WebSocket 连接。以下是常见 OneBot 实现的配置示例：

#### CQHTTP (aiocqhttp)

在 OneBot 配置文件中配置反向 WebSocket 连接：

```conf
# config.ini 或类似配置文件
[cqhttp]
# ... 其他配置 ...

# 反向 WebSocket 事件上报
ws_reverse_event_url=ws://chatguardian_host:8081/ws/event/
ws_reverse_api_url=ws://chatguardian_host:8081/ws/api/
ws_reverse_reconnect_interval=3000
ws_reverse_reconnect_on_code_5xx=true

# 访问令牌（如果配置了的话）
access_token=your_secret_token
```

#### NoneBot2

在 NoneBot `config.py` 或环境变量中配置：

```python
# config.py
CQHTTP_WS_REVERSE_EVENT_URL = "ws://chatguardian_host:8081/ws/event/"
CQHTTP_WS_REVERSE_API_URL = "ws://chatguardian_host:8081/ws/api/"
```

或通过环境变量：

```bash
export CQHTTP_WS_REVERSE_EVENT_URL="ws://chatguardian_host:8081/ws/event/"
export CQHTTP_WS_REVERSE_API_URL="ws://chatguardian_host:8081/ws/api/"
```

#### 其他 OneBot 实现

根据你使用的具体实现，查找其文档中的"反向 WebSocket"或"WebSocket 反向连接"配置选项。

### 3. 启动服务

1. **启动 ChatGuardian 服务**：
   ```bash
   poetry run chat-guardian
   ```
   或使用 uvicorn 启动 API：
   ```bash
   poetry run uvicorn chat_guardian.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
   ```

2. **启动 OneBot 实例**：
   按照 OneBot 实现的要求启动实例（例如 CQHTTP、NoneBot 等）

3. **验证连接**：
   - 查看 ChatGuardian 的日志，应该会显示：
     ```
     OneBot WebSocket connected: self_id=<qq_number>
     ```
   - 尝试在 QQ 群或私聊中发送消息，检查是否被正确接收

## 优势

### 相比于正向连接（旧方式）：

- ✅ **简化网络配置**：无需为 OneBot 实例映射端口或配置反向代理
- ✅ **防火墙友好**：OneBot 实例主动发起连接，无需入站规则
- ✅ **多实例支持**：多个 OneBot 实例可同时连接到同一个 ChatGuardian 服务
- ✅ **自动重连**：OneBot 库内置了重连机制
- ✅ **生产级别**：这是 OneBot 生态中的最佳实践

## 网络拓扑示例

### 本地测试

```
本地机器：
┌─────────────────────────────┐
│ ChatGuardian (0.0.0.0:8081) │
│ OneBot 实例                  │
└─────────────────────────────┘
```

### 分布式部署

```
OneBot 所在服务器          ChatGuardian 所在服务器
┌──────────────────┐      ┌──────────────────┐
│ OneBot 实例      │──WS──→│ ChatGuardian     │
│                  │       │ (0.0.0.0:8081)   │
└──────────────────┘       └──────────────────┘
```

## 故障排查

### 连接失败

**症状**：OneBot 实例无法连接

**排查步骤**：
1. 确认 ChatGuardian 正在运行，且监听正确的端口
2. 检查网络连通性：`ping chatguardian_host`
3. 检查防火墙规则是否允许该端口
4. 在 OneBot 实例日志中查看反向 WebSocket 连接错误信息
5. 确认访问令牌（如果配置）是否一致

### 消息未被接收

**症状**：连接成功，但消息未出现在 ChatGuardian

**排查步骤**：
1. 查看 ChatGuardian 日志中是否有消息接收记录
2. 确认在正确的群或私聊中发送消息，且 OneBot 实例有权操作
3. 检查 OneBot 实例的事件上报配置是否正确

### 端口被占用

**症状**：启动时提示端口被占用

**解决方案**：
```bash
# 修改配置中的 ONEBOT_PORT 为其他未占用的端口
CHAT_GUARDIAN_ONEBOT_PORT=8082
```

## 性能建议

- 生产环境建议使用 `0.0.0.0` 监听所有网络接口
- 如果 ChatGuardian 和 OneBot 在同一内网，可使用内网 IP
- 根据消息量调整事件处理并发数（见 `chat_guardian/settings.py` 中的 `llm_max_parallel_batches` 等参数）

## 参考文档

- [aiocqhttp 官方文档](https://aiocqhttp.nonebot.dev/module/aiocqhttp/)
- [OneBot 标准文档](https://onebot.dev/)
- [CQHTTP 实现](https://github.com/richardchien/python-aiocqhttp)
