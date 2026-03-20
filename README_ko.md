<div align="center">

![ChatGuardian](https://socialify.git.ci/Ljzd-PRO/ChatGuardian/image?description=1&font=Source+Code+Pro&forks=1&issues=1&language=1&name=1&owner=1&pattern=Diagonal+Stripes&pulls=1&stargazers=1&theme=Auto)

</div>

<h1 align="center">
  ChatGuardian
</h1>

<p align="center">
대형 언어 모델 기반의 그룹/개인 채팅 주제 감지 및 알림, 사용자 프로필 분석 시스템으로, 다양한 채팅 플랫폼의 99+ 메시지를 효율적으로 관리할 수 있습니다.
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
    <a href="./README_en.md">English</a> | <a href="./README.md">简体中文</a> | <a href="./README_zh-TW.md">繁體中文</a> | <a href="./README_ja.md">日本語</a> | 한국어 | <a href="./README_fr.md">Français</a> | <a href="./README_ru.md">Русский</a>
</p>

**현재는 테스트 단계**이며, 메시지 플랫폼 중 **OneBot**만 검증되었고, 다른 플랫폼은 아직 검증되지 않아 사용 가능 여부를 보장할 수 없습니다. 사용 후기를 환영합니다.

## ✨ 주요 기능

- 💬 그룹/개인 채팅의 **주제 감지** 규칙을 설정하여 관심 있는 주제가 언급될 때 알림 전송
  - 예: 시사 뉴스가 언급될 때, 회원 구매 재판매 예약 시작 시, 특정 게임이 언급될 때 알림
  - 감지 규칙은 **범위 제한**(개인/그룹, 그룹 번호, 참여자 등) 및 AND/OR/NOT 조합 지원
- 🤖 내장 에이전트를 통한 **한 문장으로 감지 규칙 생성**, 관리 백엔드 등
  - 내장 에이전트가 사용하는 MCP는 HTTP 서비스로 공개 가능하며, 외부 플랫폼에서 맞춤형 에이전트 제작 가능(OpenClaw, AstrBot, LangBot, CherryStudio, Dify 등)
  - [HTTP MCP 서비스는 아직 테스트되지 않음]
- 👤 **사용자 프로필 분석** 대상 그룹원을 설정하면, 해당 그룹원이 메시지를 보낼 때마다 분석이 실행됨
  - 분석 횟수가 누적될수록 프로필 정보가 더욱 완성됨

  프로필 데이터에는 다음 정보가 포함됨:
  - 해당 그룹원의 **관심 주제**
  - 해당 그룹원의 **자주 대화하는 그룹 번호**
  - 해당 그룹원이 **자주 대화하는 그룹원** 및 **주제**
- 💰 _최소 메시지 수 요구_, _최소 대기 시간 초과_, _중복 트리거 억제_ 등 맞춤형 메시지 처리로 **토큰 소비 절감**
- 💬 다양한 메시지 플랫폼 지원
  - OneBot(QQ), 기업용 위챗, Telegram, Discord, DingTalk, Feishu 등
  - [현재는 OneBot만 검증됨]
- 🔔 다양한 알림 서비스 지원
  - 이메일 알림
  - iOS Bark
  - [추가 알림 서비스 예정]
- 🤖 다양한 대형 언어 모델 플랫폼 지원
  - OpenAI
  - Antrophic
  - Google
  - OpenAI 호환 API(xAI, DeepSeek 등)

## 🔧 설치

### 🐳 Docker로 빠른 배포

```bash
docker compose up -d
```

### 💻 수동 설치

1. 의존성 설치(백엔드)

```bash
poetry install
```

2. 프론트엔드 빌드

```bash
cd frontend
npm ci --legacy-peer-deps
npm run build
```

3. 서비스 시작

```bash
poetry run uvicorn chat_guardian.api.app:app --host 0.0.0.0 --port 8000
```

> 이후 업데이트가 있을 경우, 데이터베이스 마이그레이션을 먼저 실행하세요:
>
> ```bash
> poetry run alembic upgrade head
> ```

4. 접속

- Web UI: `http://127.0.0.1:8000/app/`
