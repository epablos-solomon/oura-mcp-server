# Oura MCP Server

Servidor MCP para Oura Ring, **portable** y **multi-usuario**.

Funciona con **cualquier agente/cliente MCP** (Claude Desktop, Cursor, VS Code,
Claude Code CLI) tanto en local (stdio) como remoto (HTTP, una cuenta Oura por
persona).

## Modos de transporte

### 1) stdio (local, por defecto)

```bash
python -m oura_mcp_server
```

Un solo usuario. Usa `OURA_BEARER_TOKEN` o el `DEFAULT_USER_ID`.

### 2) HTTP (remoto, multi-usuario)

```bash
python -m oura_mcp_server --transport http
```

Expone el **protocolo MCP en `/mcp`** con autenticación Bearer, más las rutas de
OAuth y webhooks en el mismo puerto. Pensado para hospedarse (ver
[`../scaleflow-mcp-host`](../scaleflow-mcp-host)).

Endpoints HTTP: `GET /mcp` (MCP), `GET /health`, `GET|POST /auth/login`,
`GET /auth/callback`, `GET|POST /webhooks/oura`.

## Autenticación

### Multi-usuario (producción, transporte HTTP)

Dos identidades trabajan juntas:

1. **Identidad del agente** — cada agente/cliente se conecta al MCP con
   `Authorization: Bearer <api-key>`. Las keys se definen en `config/tenants.yaml`
   (ver `config/tenants.example.yaml`); cada key mapea a una persona (`user`).
2. **Cuenta Oura de la persona** — cada miembro conecta SU propio anillo. El
   link es **el mismo para todo el mundo**:

   ```
   https://oura.scaleflow.tech/auth/login
   ```

   Pega su API key en el formulario → consiente en Oura → los tokens se guardan
   server-side bajo su `user` y se refrescan solos. Nunca pega tokens a mano. El
   `state` de OAuth va firmado (HMAC) para asociar el callback a la persona
   correcta.

   La key va en el cuerpo del POST, nunca en la URL: en la query string
   acabaría escrita en los logs de acceso del proxy y en el historial del
   navegador.

Requiere en `.env`: `OURA_CLIENT_ID`, `OURA_CLIENT_SECRET`, `OURA_STATE_SECRET`,
`OURA_REDIRECT_URI` (la URL pública registrada en la app de Oura) y
`TENANTS_CONFIG_PATH`.

### Token directo (solo dev / un usuario)

Pon `OURA_BEARER_TOKEN` en `.env`. ⚠️ Expira a los 30 días; no apto para producción.

## Herramientas MCP (cobertura completa de la API v2)

**Resúmenes diarios:** `sleep_summary`, `readiness_summary`, `activity_summary`,
`spo2_summary`, `stress_summary`, `resilience_summary`, `cardiovascular_age`.
**Detalle / periodos:** `sleep_periods` (fases, HR, HRV), `sleep_time`, `workouts`,
`sessions`, `rest_mode_periods`, `vo2_max`.
**Sueño de la última noche:** `sleep_last_night` — sin argumentos elige el sueño
principal de la noche que terminó hoy (fallback al más reciente); cruza métricas
fisiológicas + score y devuelve resumen curado + JSON crudo. Admite `day` (YYYY-MM-DD).
**Serie temporal:** `heartrate` (usa `start_datetime`/`end_datetime`).
**Perfil y config:** `whoami`, `ring_configuration`.
**Etiquetas:** `enhanced_tags`, `tags` (legado).
**Agregado:** `health_snapshot` (perfil + sueño + readiness + actividad + SpO2 +
estrés + resiliencia en paralelo).
**Webhooks:** `list/create/delete/renew_webhook_subscription`.
**Prompt:** `daily_checkin`.

## Setup rápido

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                       # edita credenciales
cp config/tenants.example.yaml config/tenants.yaml   # solo para HTTP multi-usuario
python -m oura_mcp_server                  # stdio
```

## Validación

```bash
pytest -q
python -m oura_mcp_server --help
```

## Despliegue

Como contenedor dentro del host multi-MCP de Scaleflow:
[`../scaleflow-mcp-host/README.md`](../scaleflow-mcp-host/README.md).
