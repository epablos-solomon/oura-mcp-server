# Panel de administración para tenants/API keys — diseño

Fecha: 2026-09-08
Estado: aprobado, pendiente de plan de implementación

## Contexto

Hoy la gestión de tenants/API keys del Oura MCP server es 100% manual:
`config/tenants.yaml` se edita a mano por SSH en la VM `memory-mcp`, y para que
el servidor recoja los cambios hay que llamar a
`oura_mcp_server.auth.tenants.reload()` (hoy nadie lo dispara, así que en la
práctica hace falta reiniciar el contenedor). No existe ninguna vista que
cruce "qué keys existen" con "quién ya conectó su anillo Oura", ni forma de
gestionar las suscripciones de webhook sin usar las tools MCP directamente.

El servidor es pequeño (~1069 líneas), un único proceso FastMCP/Starlette que
ya expone rutas HTTP auxiliares (`/health`, `/auth/login`, `/auth/callback`,
`/webhooks/oura`) además del endpoint MCP (`/mcp`). Un solo admin (kike) lo
opera; el equipo (Scaleflow) son unas pocas personas que solo conectan su
anillo vía `/auth/login`.

## Objetivo

Un panel de administración web, accesible solo para el admin, que permita:

1. CRUD de tenants/API keys (crear, listar enmascaradas, revocar).
2. Ver el estado de conexión OAuth de cada persona (cruzando keys ↔ tokens
   guardados), y forzar una reconexión.
3. Gestionar las suscripciones de webhook de Oura (listar, crear, renovar,
   eliminar).
4. Un panel de salud/observabilidad básico (estado de config, avisos
   recientes).

## Fuera de alcance (YAGNI)

- Multi-admin / gestión de usuarios del propio panel — un solo admin, un solo
  password compartido.
- Migrar la config de tenants a una base de datos — sigue siendo YAML,
  editable a mano si hace falta.
- Logging/observabilidad persistente — ya existe `docker logs`; el panel solo
  da un vistazo rápido en memoria.
- Un servicio/contenedor separado para el admin panel — vive en el mismo
  proceso que ya sirve `/mcp` y `/auth/*`.

## Arquitectura

Rutas nuevas bajo `/admin/*`, montadas en el mismo servidor FastMCP/Starlette
(mismo contenedor, mismo dominio `oura.scaleflow.tech`, mismo Caddy). HTML
generado en Python (mismo estilo que `_FORMULARIO_LOGIN` en
`core/web_routes.py`), sin Jinja2 ni frameworks JS — no hace falta para un
solo admin y cuatro paneles simples.

Se descartó un servicio admin separado (ej. contenedor aparte): para un solo
admin y tráfico bajo, duplicar despliegue (nuevo contenedor, nueva ruta
Caddy, volúmenes compartidos) es puro overhead sin beneficio real.

### Estructura de módulo

```
src/oura_mcp_server/admin/
  __init__.py
  routes.py        # register_admin_routes(mcp, settings, store)
  auth.py          # require_admin, login/logout, rate-limit, CSRF
  templates.py     # helpers de HTML (layout, tabla, form)
  tenants_store.py # leer/escribir config/tenants.yaml con lock
```

`transports/http.py` pasa a:

```python
register_web_routes(mcp, settings, store)
register_admin_routes(mcp, settings, store)
```

## Autenticación del admin

- Password único compartido, nueva variable `ADMIN_PASSWORD` en `.env`.
- `GET/POST /admin/login`: formulario de un campo; compara con
  `secrets.compare_digest` contra `ADMIN_PASSWORD`.
- Sesión: cookie `admin_session` firmada reutilizando `sign_state`/
  `verify_state` de `auth/state.py` tal cual (payload = `"admin"`),
  expiración ~12h, flags `HttpOnly`, `Secure`, `SameSite=Lax`.
- `require_admin(request)`: guard al inicio de cada ruta `/admin/*` salvo
  `/admin/login`; sin cookie válida → redirect 302 a
  `/admin/login?next=<path>`.
- Rate-limit simple en memoria: tras 5 intentos fallidos, bloquea intentos
  nuevos 5 minutos (por proceso, sin persistencia — se resetea con el
  contenedor, es aceptable para este nivel de riesgo).
- CSRF: todo POST destructivo (revocar key, crear/renovar/eliminar webhook,
  forzar reconexión) exige un token CSRF ligado a la sesión, mismo mecanismo
  HMAC.

## CRUD de tenants / API keys

- `admin/tenants_store.py` lee `config/tenants.yaml` con `yaml.safe_load` en
  cada request de admin (no cachea entre requests), para no pisar ediciones
  manuales concurrentes por SSH.
- **Crear:** formulario (`tenant`, `user`, `agent`) → genera la key con
  `tenants.generate_api_key()` (ya existe), la agrega al `api_keys` del
  tenant, reescribe el YAML completo (`yaml.safe_dump`) y llama a
  `tenants.reload()`. La key completa se muestra **una sola vez**, en la
  página de confirmación, con aviso de que no se repetirá.
- **Listar:** cada key se muestra enmascarada
  (`sk-oura-kike-••••1a2b`) — nunca se vuelve a exponer completa.
- **Revocar:** cada fila expone un `key_id` no sensible =
  `sha256(key)[:12]` calculado al vuelo (no se persiste); el backend
  recalcula los hashes de las keys del YAML para encontrar la que coincide y
  la elimina. Así el secreto nunca vuelve a viajar en un form después de
  creado.
- Un `threading.Lock` de módulo (mismo patrón que `TokenStore._lock`)
  serializa las escrituras al YAML.
- **Limitación conocida:** `yaml.safe_dump` reescribe el archivo completo —
  cualquier comentario manual en `config/tenants.yaml` de la VM se pierde en
  el siguiente guardado desde el UI. Se deja advertido en la página.

## Estado de conexión OAuth por persona

- Nuevo método en `TokenStore`: `list_with_metadata()` — expone
  `updated_at` (columna que ya existe en la tabla `oauth_tokens` pero que
  `get()` no devuelve hoy) junto a `user_id` y los `OAuthTokens`.
- El panel cruza `TokenStore.list_with_metadata()` con las keys de
  `tenants.yaml` (por campo `user`), mostrando también keys creadas que
  nadie ha activado todavía (no solo quien ya conectó).
- Columnas: usuario, tenant/agente asociado, conectado sí/no, scopes
  concedidos, si el access token está expirado ahora mismo (informativo —
  el refresh es automático mientras haya `refresh_token`), última
  actualización.
- **Forzar reconexión** = `store.delete(user_id)`. No existe un "logout"
  real en la API de Oura; esto borra los tokens guardados y la próxima tool
  que use ese usuario falla con `user_not_connected` hasta que vuelva a
  pasar por `/auth/login`.

## Gestión de webhooks

- Confirmado en `client/oura.py`: los webhooks son a nivel de **app**
  (headers `x-client-id`/`x-client-secret`), no por usuario — el panel es
  una lista global, no por persona.
- Reutiliza `OuraClient.list_webhooks/create_webhook/delete_webhook/
  renew_webhook` tal cual, sin cambios.
- Formulario de creación con `callback_url` prellenado a
  `https://oura.scaleflow.tech/webhooks/oura` (única URL válida en este
  despliegue) y `verification_token` prellenado desde
  `settings.oura_webhook_verification_token`.
- Si `OURA_CLIENT_ID`/`OURA_CLIENT_SECRET` no están configurados, el panel
  muestra un aviso en vez de fallar con un error crudo.
- Errores de la API de Oura (`httpx.HTTPStatusError`) se capturan y se
  muestran en la página.

## Panel de salud / observabilidad

- Resultado de `/health` + presencia/ausencia (nunca el valor, salvo
  `OURA_REDIRECT_URI` que no es secreto) de: `OURA_CLIENT_ID`,
  `OURA_CLIENT_SECRET`, `OURA_STATE_SECRET`, `OURA_REDIRECT_URI`,
  `OURA_WEBHOOK_VERIFICATION_TOKEN`, `TENANTS_CONFIG_PATH`.
- Conteos: tenants, keys totales, usuarios conectados.
- Últimos ~50 `WARNING`/`ERROR` de los loggers `oura_mcp_server.*`, vía un
  `logging.Handler` en memoria (ring buffer) — se pierde al reiniciar el
  contenedor; es solo un vistazo rápido, no reemplaza `docker logs`.

## Manejo de errores (resumen transversal)

- Guard de sesión → redirect a login, nunca 500.
- Escritura de YAML falla (permisos, disco) → se captura, se muestra error
  en la página.
- Llamadas a la API de Oura fallidas → se capturan y se muestra
  status/mensaje.
- CSRF inválido/ausente en POST destructivo → rechazado explícitamente.

## Testing

Sigue el patrón existente de `tests/test_web_routes.py`: `Settings` +
`TokenStore` + `create_mcp_server` + `register_admin_routes` sobre
`tmp_path`, servido con `starlette.testclient.TestClient`, con comentarios
explicando el *por qué* de cada caso negativo.

Nuevo archivo `tests/test_admin_routes.py` cubriendo:

- Login correcto/incorrecto + rate-limit tras 5 fallos.
- `require_admin` bloquea cada ruta `/admin/*` sin sesión válida.
- Crear key → el servidor la reconoce de inmediato como Bearer válido
  (sin reiniciar) gracias a `reload()`.
- Revocar key → dejar de funcionar como Bearer inmediatamente.
- Cruce de estado OAuth con datos de fixture en `TokenStore`
  (`list_with_metadata()`).
- Panel de webhooks: creación/listado/renovación/eliminación contra un
  `OuraClient` mockeado (sin llamar a la API real de Oura en tests).
- CSRF: un POST sin token válido se rechaza.

## Variables de entorno nuevas

- `ADMIN_PASSWORD` — password compartido para acceder a `/admin/*`.

## Cambios en módulos existentes

- `auth/token_store.py`: nuevo método `list_with_metadata()` (no rompe la
  API existente).
- `transports/http.py`: registra `register_admin_routes` junto a
  `register_web_routes`.
- `config.py`: nuevo campo `admin_password: str | None`.
