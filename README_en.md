<div align="center">

![ChatGuardian](https://socialify.git.ci/Ljzd-PRO/ChatGuardian/image?custom_language=Python&description=1&font=Source+Code+Pro&forks=1&issues=1&language=1&name=1&owner=1&pattern=Diagonal+Stripes&pulls=1&stargazers=1&theme=Auto)

</div>

<h1 align="center">
  ChatGuardian
</h1>

<p align="center">
A topic detection, notification, and user profiling system for group/private chats based on large language models, helping you efficiently manage 99+ messages across various chat platforms.
</p>

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/Ljzd-PRO/ChatGuardian" alt="BSD 3-Clause"/>
  </a>

  <a href="https://github.com/Ljzd-PRO/ChatGuardian/activity">
    <img src="https://img.shields.io/github/last-commit/Ljzd-PRO/ChatGuardian/devel" alt="Last Commit"/>
  </a>
</p>

<p align="center">
    English | <a href="./README.md">简体中文</a> | <a href="./README_zh-TW.md">繁體中文</a> | <a href="./README_ja.md">日本語</a> | <a href="./README_ko.md">한국어</a> | <a href="./README_fr.md">Français</a> | <a href="./README_ru.md">Русский</a>
</p>

**Currently in testing phase**, only **OneBot** has been verified among the supported platforms. Other platforms have not been tested and may not be available. Feedback is welcome.

## ✨ Features

- 💬 Set up **topic detection** rules for group/private chats and receive notifications when your interested topics are discussed
  - For example: get notified when current events are discussed, when a pre-sale restock starts, or when a certain game is mentioned
  - Detection rules support **scoping** (private/group, group ID, participants, etc.) and logical combinations (AND/OR/NOT)
- 🤖 Built-in agent for **one-sentence rule generation** and management backend
  - The MCP used by the built-in agent can be exposed as an HTTP service, allowing you to customize your own agent on external platforms (OpenClaw, AstrBot, LangBot, CherryStudio, Dify, etc.)
  - [HTTP MCP service not yet tested]
- 👤 Set up **user profiling** for specific members; each message from them triggers an analysis
  - The more analyses, the more complete the user profile becomes

  User profile data includes:
  - The member's **topics of interest**
  - The member's **frequently used group IDs**
  - The member's **frequent chat partners** and **topics discussed**
- 💰 Customizable message handling mechanisms such as _minimum message count_, _minimum wait timeout_, _duplicate trigger suppression_, etc., to **save your token consumption**
- 💬 Supports multiple chat platforms
  - OneBot (QQ), WeCom, Telegram, Discord, DingTalk, Feishu, etc.
  - [Currently only OneBot has been tested]
- ⚙ All configuration items can be set through the WebUI interface without setting environment variables, simple and convenient
- 🔔 Supports multiple notification services
  - Email notification
  - iOS Bark
  - [More notification services coming soon]
- 🤖 Supports multiple LLM platforms
  - OpenAI
  - Antrophic
  - Google
  - OpenAI-compatible APIs (xAI, DeepSeek, etc.)

## 🔧 Installation

### 🐳 Quick Deploy with Docker

```bash
git clone https://github.com/Ljzd-PRO/ChatGuardian.git --depth 1
cd ChatGuardian
docker compose up -d
```

The database file `db.sqlite` will be created in the `ChatGuardian/data` directory.

If you update later, database definitions may change and migrations may be executed during startup, so it's recommended to back up the `db.sqlite` file before updating.

### 💻 Manual Installation

1. Clone the repository

    ```bash
    git clone https://github.com/Ljzd-PRO/ChatGuardian.git --depth 1
    cd ChatGuardian
    ```

2. Install dependencies (backend)

    ```bash
    poetry install
    ```

3. Build frontend

    ```bash
    cd frontend
    npm ci --legacy-peer-deps
    npm run build
    cd ..
    ```

4. Start the service

    ```bash
    poetry run uvicorn chat_guardian.api.app:app --host 0.0.0.0 --port 8000
    ```

    If you update later, database definitions may change and migrations may be executed during startup, so it's recommended to back up the `db.sqlite` file before updating.

5. Access

    Web UI: `http://127.0.0.1:8000/app/`
