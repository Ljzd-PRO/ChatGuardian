<div align="center">

![ChatGuardian](https://socialify.git.ci/Ljzd-PRO/ChatGuardian/image?custom_language=Python&description=1&font=Source+Code+Pro&forks=1&issues=1&language=1&name=1&owner=1&pattern=Diagonal+Stripes&pulls=1&stargazers=1&theme=Auto)

</div>

<h1 align="center">
  ChatGuardian
</h1>

<p align="center">
大規模言語モデルに基づくグループ/プライベートチャットのトピック検出と通知、ユーザープロファイリングシステムで、99+の各種チャットプラットフォームのメッセージを効率的に管理できます。
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
    <a href="./README_en.md">English</a> | <a href="./README.md">简体中文</a> | <a href="./README_zh-TW.md">繁體中文</a> | 日本語 | <a href="./README_ko.md">한국어</a> | <a href="./README_fr.md">Français</a> | <a href="./README_ru.md">Русский</a>
</p>

**現在はテスト段階です**。メッセージプラットフォームでは**OneBot**のみが検証済みで、他のプラットフォームは未検証のため、利用可能かどうかは保証できません。ご意見・ご感想をお待ちしています。

## ✨ 機能特徴

- 💬 グループ/プライベートチャットの**トピック検出**ルールを設定し、興味のある話題が出たときに通知
  - 例：時事ニュースが話題になったとき、会員購入の再販予約開始時、特定のゲームが話題になったときに通知
  - 検出ルールは**範囲限定**（プライベート/グループ、グループID、参加者など）やAND/OR/NOTの組み合わせに対応
- 🤖 内蔵エージェントによる**ワンフレーズで検出ルール生成**や管理画面など
  - 内蔵エージェントが使用するMCPはHTTPサービスとして公開可能で、外部プラットフォームで独自エージェントをカスタマイズできます（OpenClaw, AstrBot, LangBot, CherryStudio, Difyなど）
  - 【HTTP MCPサービスは未検証】
- 👤 **ユーザープロファイリング**対象のユーザーを設定し、そのユーザーがメッセージを送信するたびに分析を実行
  - 分析回数が増えるほど、ユーザープロファイルが充実します

  プロファイルデータには以下の情報が含まれます：
  - ユーザーの**興味のある話題**
  - ユーザーの**よく使うグループID**
  - ユーザーが**よくやり取りする相手**とその**話題**
- 💰 _最小メッセージ数要件_、_最小待機タイムアウト_、_重複トリガー抑制_など、カスタマイズ可能なメッセージ処理で**トークン消費を節約**
- 💬 複数のメッセージプラットフォームに対応
  - OneBot（QQ）、WeCom、Telegram、Discord、DingTalk、Feishuなど
  - 【現在はOneBotのみ検証済み】
- 🔔 多様な通知サービスに対応
  - メール通知
  - iOS Bark
  - 【今後さらに追加予定】
- 🤖 多様な大規模言語モデルプラットフォームに対応
  - OpenAI
  - Antrophic
  - Google
  - OpenAI互換API（xAI, DeepSeekなど）

## 🔧 インストール

### 🐳 Dockerで簡単デプロイ

```bash
git clone https://github.com/Ljzd-PRO/ChatGuardian.git
cd ChatGuardian
docker compose up -d
```

### 💻 手動インストール

1. 依存関係のインストール（バックエンド）

```bash
poetry install
```

2. フロントエンドのビルド

```bash
cd frontend
npm ci --legacy-peer-deps
npm run build
```

3. サービスの起動

```bash
poetry run uvicorn chat_guardian.api.app:app --host 0.0.0.0 --port 8000
```

> 後で更新があった場合は、データベースのマイグレーションを実行してください：
>
> ```bash
> poetry run alembic upgrade head
> ```

4. アクセス

- Web UI: `http://127.0.0.1:8000/app/`
