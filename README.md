# Oura MCP Server

Servidor MCP portable para Oura Ring.

Funciona con **cualquier agente/cliente MCP**: Claude Desktop, Cursor,
VS Code, Claude Code CLI, y cualquier otro que soporte el protocolo MCP.

## Modos de uso

### 1) MCP stdio (por defecto - recomendado)

```bash
python -m oura_mcp_server
```

Conectalo desde cualquier cliente MCP apuntando a:
```bash
python -m oura_mcp_server
```

### 2) HTTP / FastAPI
Para OAuth callback, webhooks y healthcheck:

```bash
python -m oura_mcp_server --transport http
```

## Autenticacion

### Modo OAuth2 (produccion)
1. Registra una app en https://cloud.ouraring.com/oauth/applications
2. Configura `OURA_CLIENT_ID` y `OURA_CLIENT_SECRET` en `.env`
3. Corre el servidor en modo HTTP: `python -m oura_mcp_server --transport http`
4. Visita `http://localhost:8000/auth/login`
5. Autoriza la app en Oura
6. Listo. Los tokens se refrescan automaticamente.

### Modo token directo (solo dev)
Si no quieres configurar OAuth2 completo:
1. Genera un access token desde el dashboard de Oura (developer tools)
2. Ponlo en `OURA_BEARER_TOKEN` en `.env`
3. Corre el servidor: `python -m oura_mcp_server`

⚠️ El token directo expira a los 30 dias. No apto para produccion.

## Herramientas MCP

| Herramienta | Descripcion |
|---|---|
| `whoami` | Perfil del usuario conectado |
| `sleep_summary` | Resumen de sueno por dia |
| `activity_summary` | Resumen de actividad por dia |
| `health_snapshot` | Snapshot completo salud + sueno + actividad |
| `list_webhook_subscriptions` | Lista webhooks activos |
| `create_webhook_subscription` | Crea un webhook |
| `renew_webhook_subscription` | Renueva un webhook |
| `delete_webhook_subscription` | Elimina un webhook |

## Setup rapido

```bash
pip install -e .[dev]
cp .env.example .env
# edita .env con tus credenciales
python -m oura_mcp_server
```

## Validacion

```bash
python -m compileall src tests
pytest -v
python -m oura_mcp_server --help
```
