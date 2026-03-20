<div align="center">

![ChatGuardian](https://socialify.git.ci/Ljzd-PRO/ChatGuardian/image?custom_language=Python&description=1&font=Source+Code+Pro&forks=1&issues=1&language=1&name=1&owner=1&pattern=Diagonal+Stripes&pulls=1&stargazers=1&theme=Auto)

</div>

<h1 align="center">
  ChatGuardian
</h1>

<p align="center">
Système d'analyse de sujets de discussion et de profil utilisateur basé sur des modèles de langage avancés, pour gérer efficacement les messages 99+ sur diverses plateformes de chat.
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
    <a href="./README_en.md">English</a> | <a href="./README.md">简体中文</a> | <a href="./README_zh-TW.md">繁體中文</a> | <a href="./README_ja.md">日本語</a> | <a href="./README_ko.md">한국어</a> | Français | <a href="./README_ru.md">Русский</a>
</p>

**Actuellement en phase de test**, seule la plateforme **OneBot** a été vérifiée, les autres plateformes n'ont pas encore été testées et leur disponibilité n'est pas garantie. N'hésitez pas à faire part de vos retours.

## ✨ Fonctionnalités

- 💬 Définissez des règles de **détection de sujets** pour les discussions de groupe/privées et recevez des notifications lorsque des sujets d'intérêt sont abordés
  - Par exemple : être averti lors de discussions sur l'actualité, les rééditions de préventes, ou certains jeux
  - Les règles de détection prennent en charge la **délimitation** (privé/groupe, numéro de groupe, participants, etc.) et la combinaison logique (ET/OU/NON)
- 🤖 Génération de règles de détection et gestion via un agent intégré
  - Les MCP utilisés par l'agent intégré peuvent être exposés en tant que service HTTP, vous permettant de personnaliser vos propres agents sur d'autres plateformes (OpenClaw, AstrBot, LangBot, CherryStudio, Dify, etc.)
  - [Service HTTP MCP non testé]
- 👤 Analyse de profil utilisateur pour des membres spécifiques, déclenchée à chaque message envoyé
  - Plus l'analyse est fréquente, plus le profil utilisateur est complet

  Les données de profil incluent :
  - Les **sujets d'intérêt** de l'utilisateur
  - Les **groupes fréquemment utilisés**
  - Les **interlocuteurs fréquents** et les **sujets abordés**
- 💰 _Nombre minimal de messages_, _délai d'attente minimal_, _suppression des déclenchements répétés_, etc., pour économiser vos tokens
- 💬 Prise en charge de plusieurs plateformes de messagerie
  - OneBot (QQ), WeCom, Telegram, Discord, DingTalk, Feishu, etc.
  - [Seul OneBot a été testé pour l'instant]
- ⚙ Tous les éléments de configuration peuvent être définis par l'interface WebUI sans définir les variables d'environnement, simple et pratique
- 🔔 Prise en charge de plusieurs services de notification
  - Notification par e-mail
  - iOS Bark
  - [D'autres services à venir]
- 🤖 Prise en charge de plusieurs plateformes de grands modèles de langage
  - OpenAI
  - Antrophic
  - Google
  - API compatibles OpenAI (xAI, DeepSeek, etc.)

## 🔧 Installation

### 🐳 Déploiement rapide avec Docker

```bash
git clone https://github.com/Ljzd-PRO/ChatGuardian.git --depth 1
cd ChatGuardian
docker compose up -d
```

Le fichier de base de données `db.sqlite` sera créé dans le répertoire `ChatGuardian/data`

Si une mise à jour a lieu, la définition de la base de données peut changer et une migration peut être exécutée au démarrage. Il est donc recommandé de sauvegarder le fichier `db.sqlite` avant la mise à jour.

### 💻 Installation manuelle

1. Cloner le référentiel

    ```bash
    git clone https://github.com/Ljzd-PRO/ChatGuardian.git --depth 1
    cd ChatGuardian
    ```

2. Installer les dépendances (backend)

    ```bash
    poetry install
    ```

3. Construire le frontend

    ```bash
    cd frontend
    npm ci --legacy-peer-deps
    npm run build
    cd ..
    ```

4. Démarrer le service

    ```bash
    poetry run uvicorn chat_guardian.api.app:app --host 0.0.0.0 --port 8000
    ```

    Si une mise à jour a lieu, la définition de la base de données peut changer et une migration peut être exécutée au démarrage. Il est donc recommandé de sauvegarder le fichier `db.sqlite` avant la mise à jour.

5. Accéder à l'interface Web

    Web UI : `http://127.0.0.1:8000/app/`
