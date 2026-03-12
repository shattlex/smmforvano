# Деплой в Cloud Run (общий доступ по URL)

## 1) Подготовить GCP

```bash
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 2) Создать Artifact Registry

```bash
gcloud artifacts repositories create seed-monitor \
  --repository-format=docker \
  --location=europe-west3 \
  --description="Seed monitor images"
```

## 3) Подготовить PostgreSQL

Используйте любой доступный managed PostgreSQL (Cloud SQL/Neon/Supabase).

Нужен URL вида:

```text
postgresql://USER:PASSWORD@HOST:5432/seed_monitor
```

## 4) Задать переменные деплоя

```bash
export PROJECT_ID=$(gcloud config get-value project)
export REGION=europe-west3
export SERVICE=seed-monitor
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/seed-monitor/seed-monitor:latest"

export DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/seed_monitor'
export SESSION_SECRET='CHANGE_ME_LONG_RANDOM_SECRET'
export ADMIN_EMAIL='you@company.com'
export ADMIN_PASSWORD='CHANGE_ME_STRONG_PASSWORD'
```

## 5) Build + Deploy

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions _SERVICE=${SERVICE},_REGION=${REGION},_IMAGE=${IMAGE},_DATABASE_URL="${DATABASE_URL}",_SESSION_SECRET="${SESSION_SECRET}",_ADMIN_EMAIL="${ADMIN_EMAIL}",_ADMIN_PASSWORD="${ADMIN_PASSWORD}"
```

## 6) Получить ссылку для коллеги

```bash
gcloud run services describe ${SERVICE} --region ${REGION} --format='value(status.url)'
```

Вы получите URL вида:

```text
https://seed-monitor-xxxxx-ew.a.run.app
```

Коллега открывает эту ссылку и логинится по `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## 7) Что сделать после первого входа

1. Внести реальные `seed` ящики и app passwords.
2. Внести кампании (`subject` + `cid_token`).
3. Нажать `Run Check`.

## 8) Рекомендация по безопасности

- Замените дефолтный админ-пароль на сильный.
- Задайте длинный `SESSION_SECRET`.
- При необходимости закройте публичный доступ и поставьте IAP/Cloud Armor.
