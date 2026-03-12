# Seed Deliverability Monitor

Система мониторинга доставляемости email-кампаний по контрольным Gmail seed-ящикам.

## Функционал

- Сбор статусов: `INBOX`, `SPAM`, `DELIVERED_NOT_INBOX`, `NOT_DELIVERED`, `ERROR_AUTH`.
- Поиск по `cid_token` (приоритетно) и `subject`.
- История запусков и детальные результаты.
- Веб-интерфейс с KPI и таблицами.
- Авторизация (email + password, cookie session).
- Поддержка `SQLite` (локально) и `PostgreSQL` (облако).

## Локальный запуск

```bash
cd seed-monitor-git-ready
python3 scripts/init_db.py
python3 scripts/run_server.py
```

Открыть:

- `http://127.0.0.1:8080`
- логин: `ADMIN_EMAIL` / `ADMIN_PASSWORD` (из env, по умолчанию в `.env.example`)

## Облачный запуск для команды

См. инструкцию:

- [DEPLOY_CLOUDRUN.md](./DEPLOY_CLOUDRUN.md)

После деплоя коллега получает один URL и входит под своей учёткой.

## Ключевые файлы

- Backend: `app/`
- Frontend: `web/`
- Деплой: `Dockerfile`, `cloudbuild.yaml`, `.env.example`

## Важно

Перед боевой эксплуатацией:

1. Заполните реальные seed-ящики и app passwords.
2. Используйте уникальный `cid_token` в теме кампании.
3. В облаке используйте PostgreSQL, а не SQLite.
