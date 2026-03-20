<div align="center">

![ChatGuardian](https://socialify.git.ci/Ljzd-PRO/ChatGuardian/image?custom_language=Python&description=1&font=Source+Code+Pro&forks=1&issues=1&language=1&name=1&owner=1&pattern=Diagonal+Stripes&pulls=1&stargazers=1&theme=Auto)

</div>

<h1 align="center">
  ChatGuardian
</h1>

<p align="center">
基於大模型的群聊/私聊話題檢測與提醒、用戶畫像分析系統，讓您高效地管理消息 99+ 的各種聊天平台。
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
    <a href="./README_en.md">English</a> | <a href="./README.md">简体中文</a> | 繁體中文 | <a href="./README_ja.md">日本語</a> | <a href="./README_ko.md">한국어</a> | <a href="./README_fr.md">Français</a> | <a href="./README_ru.md">Русский</a>
</p>

**目前仍為測試階段**，消息平台中只有**OneBot**進行了驗證，其他消息平台尚未經過驗證，不能確保可用。歡迎反饋使用體驗。

## ✨ 功能特性

- 💬 設定群聊/私聊**話題檢測**規則，當群裡聊到自己感興趣的話題時發送通知
  - 例如：當聊到時事新聞時提醒、當聊到會員購再版預售開始時提醒、當聊到某遊戲時提醒
  - 檢測規則支援**限定範圍**（私聊/群聊、群號、參與群友等），並且支援與或非關係疊加
- 🤖 透過內建的智能體，**一句話生成檢測規則**，管理後台等
  - 內建智能體所用 MCP 均可作為 HTTP 服務開放，您可以在外部平台自訂自己的智能體（如 OpenClaw, AstrBot, LangBot, CherryStudio, Dify 等）
  - 【HTTP MCP 服務暫未經過測試】
- 👤 設定需要進行**用戶畫像分析**的群友，每當該群友發送消息時就會觸發一次分析
  - 隨著分析次數的累積，該群友的用戶畫像資訊會非常完善

  用戶畫像資料大致包含以下資訊：
  - 該群友**感興趣的話題**
  - 該群友**常聊的群號**
  - 該群友**經常與哪些群友**聊天互動，都聊些什麼**話題**
- 💰 _消息最小數量要求_、_等待最小消息超時_、_重複觸發抑制_ 等支援自訂的消息處理機制，能夠**節省您的 Token 消耗**
- 💬 支援多個消息平台
  - OneBot（QQ）、企業微信、Telegram、Discord、釘釘、飛書 等
  - 【目前僅 OneBot 經過了測試】
- ⚙ 所有配置項均可透過 WebUI 界面進行設定，無需設定環境變數，簡單方便
- 🔔 支援多種通知服務
  - 郵件通知
  - iOS Bark
  - 【更多通知服務待實現～】
- 🤖 支援多種大模型平台
  - OpenAI
  - Antrophic
  - Google
  - OpenAI 相容 API（xAI, DeepSeek 等）

## 🔧 安裝

### 🐳 Docker 快速部署

```bash
git clone https://github.com/Ljzd-PRO/ChatGuardian.git --depth 1
cd ChatGuardian
docker compose up -d
```

資料庫檔案 `db.sqlite` 將被建立在 `ChatGuardian/data` 目錄下

若後續進行了更新，資料庫定義可能發生變化，啟動時可能執行遷移，因此建議在更新前對 `db.sqlite` 檔案進行備份

### 💻 手動安裝

1. 複製項目

    ```bash
    git clone https://github.com/Ljzd-PRO/ChatGuardian.git --depth 1
    cd ChatGuardian
    ```

2. 安裝依賴（後端）

    ```bash
    poetry install
    ```

3. 構建前端

    ```bash
    cd frontend
    npm ci --legacy-peer-deps
    npm run build
    cd ..
    ```

4. 啟動服務

    ```bash
    poetry run uvicorn chat_guardian.api.app:app --host 0.0.0.0 --port 8000
    ```

    若後續進行了更新，資料庫定義可能發生變化，啟動時可能執行遷移，因此建議在更新前對 `db.sqlite` 檔案進行備份

5. 訪問

    Web UI: `http://127.0.0.1:8000/app/`
