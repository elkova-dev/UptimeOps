# UptimeOps - результат повторной проверки

- Исходные папки: `src/`, `frontend/`, `tests/`, `docs/`.
- Тесты проверяют основные HTTP API, контракты JSON, инциденты, миграции SQLite, обработку HTTP редиректов.
- Для запуска: `RUN_ME_WINDOWS.bat` (Windows) или инструкции в README (Linux/macOS).
- В GitHub Actions проверяется наличие исходников, установка библиотек, pytest и GET `/`.
- Поддержка GUI на macOS/Windows/Linux и Docker на данном этапе автоматически не подтверждена: проверяйте после публикации в GitHub.
- Приложение локальное, без авторизации, не публикуйте его сервер на общедоступном адресе.

## Как обновить публичный репозиторий

1. Откройте свою папку `UptimeOps-fix`, клонированную из GitHub.
2. Скопируйте всё содержимое новой папки `UptimeOps/` в `UptimeOps-fix/`, согласившись на обновление файлов. Не удаляйте `.git`.
3. Из старых workflow удалите `python-tests.yml`, если присутствует.
4. В PowerShell из `UptimeOps-fix` выполните: `git status`; затем `git add -A`; `git status`; `git commit -m "Restore sources and add cross-platform tests"`; `git push`.
5. Перейдите в GitHub Actions и проверьте результат.

Не загружайте `.venv`, `data`, `.git`, токены и файлы `.env`.
