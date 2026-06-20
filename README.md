# Oura MCP Server

Base inicial de un servidor MCP para integrar Oura Ring.

## Fase 2
- Persistencia SQLite de tokens
- Refresh automático de tokens
- Health snapshot unificado
- Administración básica de webhooks

## Qué incluye
- OAuth2 server-side para Oura
- Healthcheck HTTP
- Webhook endpoint base
- Tools MCP para perfil y resúmenes diarios
- Tools MCP para webhooks

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

## Variables de entorno
- `OURA_CLIENT_ID`
- `OURA_CLIENT_SECRET`
- `OURA_REDIRECT_URI`
- `OURA_WEBHOOK_VERIFICATION_TOKEN`
- `OURA_SCOPES`
- `OURA_TOKEN_DB_PATH`

## Correr API

```bash
uvicorn app.main:app --reload --port 8000
```

## Correr MCP

```bash
python -m app.mcp_server
```

## Pruebas

```bash
pytest -q
```

## Flujo
1. Llamar `GET /oauth/start?user_id=...`
2. Autorizar en Oura
3. Recibir `GET /oauth/callback`
4. Usar los tools MCP para consultar perfil, métricas y snapshot

## Endpoints útiles
- `GET /tokens/users`
- `GET /webhooks/oura/subscriptions`
- `POST /webhooks/oura/subscriptions`
- `DELETE /webhooks/oura/subscriptions/{id}`
- `PUT /webhooks/oura/subscriptions/{id}/renew`

## Siguientes pasos
- Manejo de errores 401/403/429 más fino
- Reintentos y backoff
- Normalización de respuestas Oura
- Persistir eventos de webhook para re-sync
