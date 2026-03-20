<div align="center">

![ChatGuardian](https://socialify.git.ci/Ljzd-PRO/ChatGuardian/image?custom_language=Python&description=1&font=Source+Code+Pro&forks=1&issues=1&language=1&name=1&owner=1&pattern=Diagonal+Stripes&pulls=1&stargazers=1&theme=Auto)

</div>

<h1 align="center">
  ChatGuardian
</h1>

<p align="center">
Система обнаружения тем и анализа профиля пользователя на основе больших языковых моделей, позволяющая эффективно управлять сообщениями 99+ на различных платформах чата.
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
    <a href="./README_en.md">English</a> | <a href="./README.md">简体中文</a> | <a href="./README_zh-TW.md">繁體中文</a> | <a href="./README_ja.md">日本語</a> | <a href="./README_ko.md">한국어</a> | <a href="./README_fr.md">Français</a> | Русский
</p>

**В настоящее время проект находится на стадии тестирования**, только платформа **OneBot** была проверена, остальные платформы еще не тестировались, поэтому их работоспособность не гарантируется. Будем рады вашим отзывам.

## ✨ Особенности

- 💬 Настройка правил **обнаружения тем** для групповых/личных чатов с уведомлениями при обсуждении интересующих тем
  - Например: уведомление при обсуждении новостей, начале предзаказа, обсуждении определенной игры
  - Поддержка **ограничения области** (личный/групповой чат, номер группы, участники и др.), а также логических связок (И/ИЛИ/НЕ)
- 🤖 Генерация правил обнаружения и управление через встроенного агента
  - MCP, используемые встроенным агентом, могут быть доступны как HTTP-сервис, вы можете создавать собственных агентов на внешних платформах (OpenClaw, AstrBot, LangBot, CherryStudio, Dify и др.)
  - [HTTP MCP сервис не тестировался]
- 👤 Анализ профиля пользователя для выбранных участников, выполняется при каждом их сообщении
  - Чем больше анализов, тем полнее профиль пользователя

  Данные профиля включают:
  - **Интересующие темы** пользователя
  - **Часто используемые группы**
  - **Часто взаимодействующие участники** и обсуждаемые **темы**
- 💰 _Минимальное количество сообщений_, _минимальное время ожидания_, _подавление повторных срабатываний_ и др. для экономии токенов
- 💬 Поддержка различных платформ обмена сообщениями
  - OneBot (QQ), WeCom, Telegram, Discord, DingTalk, Feishu и др.
  - [Пока протестирован только OneBot]
- ⚙ Все элементы конфигурации можно установить через интерфейс WebUI без установки переменных окружения, просто и удобно
- 🔔 Поддержка различных сервисов уведомлений
  - Уведомления по электронной почте
  - iOS Bark
  - [Больше сервисов в будущем]
- 🤖 Поддержка различных платформ больших языковых моделей
  - OpenAI
  - Antrophic
  - Google
  - Совместимые с OpenAI API (xAI, DeepSeek и др.)

## 🔧 Установка

### 🐳 Быстрый запуск через Docker

```bash
git clone https://github.com/Ljzd-PRO/ChatGuardian.git --depth 1
cd ChatGuardian
docker compose up -d
```

Файл базы данных `db.sqlite` будет создан в директории `ChatGuardian/data`

Если произойдет обновление, определение базы данных может измениться, и во время запуска может выполниться миграция, поэтому рекомендуется создавать резервную копию файла `db.sqlite` перед обновлением.

### 💻 Ручная установка

1. Клонирование репозитория

    ```bash
    git clone https://github.com/Ljzd-PRO/ChatGuardian.git --depth 1
    cd ChatGuardian
    ```

2. Установка зависимостей (backend)

    ```bash
    poetry install
    ```

3. Сборка frontend

    ```bash
    cd frontend
    npm ci --legacy-peer-deps
    npm run build
    cd ..
    ```

4. Запуск сервиса

    ```bash
    poetry run uvicorn chat_guardian.api.app:app --host 0.0.0.0 --port 8000
    ```

    Если произойдет обновление, определение базы данных может измениться, и во время запуска может выполниться миграция, поэтому рекомендуется создавать резервную копию файла `db.sqlite` перед обновлением.

5. Доступ

    Web UI: `http://127.0.0.1:8000/app/`
