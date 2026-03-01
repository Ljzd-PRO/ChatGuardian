# OneBot 适配器反向 WebSocket 连接方式改造总结

## 改造完成

根据官方文档 https://aiocqhttp.nonebot.dev/module/aiocqhttp/，已成功将 OneBot 适配器改为使用**反向 WebSocket 连接方式**，ChatGuardian 现在作为 WebSocket 服务端，让 OneBot 实例主动连接。

## 修改清单

### 1. [chat_guardian/adapters/onebot.py](chat_guardian/adapters/onebot.py)

#### 配置类更改
- **移除了**：`api_root`（OneBot API 根地址）、`retry_interval_seconds`、`connect_timeout_seconds`
- **新增了**：
  - `host`：WebSocket 服务器监听地址（默认：`127.0.0.1`）
  - `port`：WebSocket 服务器监听端口（默认：`8081`）
- **保留了**：`access_token`（可选的访问令牌）

#### 适配器类更改
- **移除了**：
  - `_retry_task`：不再需要定期轮询检查连接
  - `_retry_connect_loop()` 方法：已删除
  
- **新增了**：
  - `_server_task`：用于追踪 WebSocket 服务器任务
  - `@self._bot.on_websocket_connection`：WebSocket 连接成功时的回调函数
  
- **修改了**：
  - `__init__()`：初始化 CQHttp 时不再需要 `api_root`
  - `start()`：改为启动内置的 Quart 服务器（使用 `self._bot.run_task()`）
  - `stop()`：更新为取消 `_server_task` 而非 `_retry_task`
  - `_register_bot_callbacks()`：新增 WebSocket 连接事件处理

### 2. [chat_guardian/settings.py](chat_guardian/settings.py)

#### OneBot 配置变动
- **移除了**：
  - `onebot_api_root`：不再需要 API 根地址
  - `onebot_retry_interval_seconds`：轮询重试间隔（不再使用）
  - `onebot_connect_timeout_seconds`：连接超时时间（不再使用）
  
- **新增了**：
  - `onebot_host`：WebSocket 服务器监听地址（默认：`127.0.0.1`）
  - `onebot_port`：WebSocket 服务器监听端口（默认：`8081`）
  
- **保留了**：
  - `onebot_access_token`：可选的访问令牌

#### 环境变量前缀
- `CHAT_GUARDIAN_ONEBOT_HOST`
- `CHAT_GUARDIAN_ONEBOT_PORT`
- `CHAT_GUARDIAN_ONEBOT_ACCESS_TOKEN`

### 3. [chat_guardian/adapters/__init__.py](chat_guardian/adapters/__init__.py)

#### 初始化代码更新
- 移除了 `api_root` 验证检查
- 更新了 `OneBotAdapterConfig` 初始化，使用新的 `host` 和 `port` 参数
- 移除了 `retry_interval_seconds` 和 `connect_timeout_seconds` 参数

## 工作流程变化

### 原始方式（定向连接）
```
ChatGuardian (客户端)  →  HTTP/WebSocket  →  OneBot 实例 (服务端)
```
- ChatGuardian 主动连接到 OneBot 实例的 HTTP API
- 定期轮询检查连接状态
- 需要知道 OneBot 实例的确切地址

### 新方式（反向 WebSocket）
```
OneBot 实例 (客户端)  →  WebSocket  →  ChatGuardian (服务端)
                        ws://host:port/ws/event/
```
- OneBot 实例主动连接到 ChatGuardian 的 WebSocket 服务器
- WebSocket 协议自动处理心跳和重连
- ChatGuardian 作为服务端被动接收连接

## 配置示例

### .env 文件
```env
# OneBot 反向 WebSocket 服务器配置
CHAT_GUARDIAN_ONEBOT_HOST=0.0.0.0
CHAT_GUARDIAN_ONEBOT_PORT=8081
CHAT_GUARDIAN_ONEBOT_ACCESS_TOKEN=your_secret_token
CHAT_GUARDIAN_ENABLED_ADAPTERS=onebot
```

### OneBot/CQHTTP 配置文件
```conf
[cqhttp]
ws_reverse_event_url=ws://chatguardian_host:8081/ws/event/
ws_reverse_api_url=ws://chatguardian_host:8081/ws/api/
access_token=your_secret_token
```

## 优势总结

✅ **网络拓扑简化**：无需为 OneBot 实例配置反向代理或端口映射  
✅ **防火墙友好**：OneBot 主动发起连接，符合多数防火墙出站规则  
✅ **多实例支持**：多个 OneBot 实例可同时连接到单个 ChatGuardian 服务  
✅ **更优雅的故障处理**：WebSocket 内置心跳和自动重连机制  
✅ **生产就绪**：遵循 OneBot 生态的最佳实践  

## 额外资源

- 详细配置指南：[ONEBOT_REVERSE_WEBSOCKET_SETUP.md](ONEBOT_REVERSE_WEBSOCKET_SETUP.md)
- 官方 aiocqhttp 文档：https://aiocqhttp.nonebot.dev/module/aiocqhttp/
- OneBot 标准：https://onebot.dev/

## 向后兼容性

⚠️ **破坏性变更**：此改造改变了 OneBot 适配器的配置方式，需要更新现有的配置和部署。

### 迁移步骤
1. 更新环境变量，使用新的 `onebot_host` 和 `onebot_port` 替代 `onebot_api_root`
2. 配置 OneBot 实例指向新的 WebSocket 服务器地址
3. 移除任何旧的 API 轮询代码或脚本

## 测试

建议进行以下测试：
1. ✅ WebSocket 连接建立
2. ✅ 消息接收
3. ✅ 事件处理
4. ✅ 异常重连机制
5. ✅ 多实例并发连接
