# Инструменты для Данияла — Windows 11

В PowerShell должны быть доступны `git`, `node`, `npx.cmd` и `codex`. Команды ниже выполняются по одной; уже настроенные инструменты повторно добавлять не нужно. Плагины устанавливаются через Codex CLI или приложение; после установки начните новую сессию Codex.
- Документация библиотек: `codex mcp add context7 -- npx.cmd -y @upstash/context7-mcp@latest` — [Context7](https://github.com/upstash/context7).
- Проверка UI через установленный Microsoft Edge: `codex mcp add playwright -- npx.cmd -y @playwright/mcp@0.0.82 --browser msedge --headless --isolated` — [Playwright MCP](https://github.com/microsoft/playwright-mcp).
- Документация OpenAI: `codex mcp add openaiDeveloperDocs --url https://developers.openai.com/mcp` — [официальная инструкция](https://developers.openai.com/learn/docs-mcp).
- Каталог навыков: `codex plugin marketplace add wshobson/agents` — [исходный репозиторий](https://github.com/wshobson/agents).
- Python: `codex plugin add python-development@claude-code-workflows`.
- FastAPI: `codex plugin add api-scaffolding@claude-code-workflows`. Используйте только зафиксированный в AGENTS.md стек; примеры Postgres, GraphQL и дополнительных сервисов не переносите в проект.
- Проверка конфигурации: `codex mcp list` и `codex plugin list`. В новой сессии попросите найти документацию FastAPI через Context7 и открыть `about:blank` через Playwright. Windows-настройку должен проверить Даниял на своём ноутбуке.
- GitHub: обычный Git уже достаточен для совместной работы; каждый входит под своим аккаунтом. API-ключи не нужны для OpenAI Docs MCP и не передаются партнёру.
- На Mac проверены Context7 и запуск Playwright в Chromium; OpenAI Docs MCP добавлен и ответил на инициализацию. Уже установлены Python/FastAPI/backend, PDF, документы, таблицы, презентации; навыки дизайна доступны. Эти инструменты разработки не являются зависимостями приложения.
