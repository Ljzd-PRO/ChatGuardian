# ChatGuardian

基于大模型的群聊/私聊规则检测与提醒、用户画像分析系统，让您高效地管理消息 99+ 的各种聊天平台。

**当前仍是测试阶段**，消息平台中只有**OneBot**进行了验证，其他消息平台尚未经过验证，不能确保可用。欢迎反馈使用体验。

## ✨ 功能特性

- 💬 设置群聊/私聊**话题检测**规则，当群里聊到自己感兴趣的话题时发送通知
  - 例如：当聊到时事新闻时提醒、当聊到会员购再版预售开始时提醒、当聊到某游戏时提醒
- 👤 设置需要进行**用户画像分析**的群友，每当该群友发送消息时就会触发一次分析
  - 随着分析次数的积累，该群友的用户画像信息会非常完善

  用户画像数据大致包含以下信息：
  - 该群友**感兴趣的话题**
  - 该群友**常聊的群号**
  - 该群友**经常与哪些群友**聊天互动，都聊些什么**话题**
- 💬 支持多个消息平台
  - OneBot（QQ）、企业微信、Telegram、Discord、钉钉、飞书 等
- 🔔 支持多种通知服务
  - 邮件通知
  - iOS Bark
- 🤖 支持多种大模型平台
  - OpenAI
  - Antrophic
  - Google
  - OpenAI 兼容 API（xAI, DeepSeek 等）

## 🔧 安装

### 🐳 Docker 快速部署

```bash
docker compose up -d
```

### 💻 手动安装

1. 安装依赖（后端）

```bash
poetry install
```

2. 构建前端

```bash
cd frontend
npm ci --legacy-peer-deps
npm run build
```

3. 启动服务

```bash
poetry run uvicorn chat_guardian.api.app:app --host 0.0.0.0 --port 8000
```

> 若后续进行了更新，则需要先执行数据库迁移：
>
> ```bash
> poetry run alembic upgrade head
> ```

4. 访问

- Web UI: `http://127.0.0.1:8000/app/`
