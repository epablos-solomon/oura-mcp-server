from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier

from oura_mcp_server.auth.identity import resolve_user_id
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.client.oura import OuraClient
from oura_mcp_server.config import Settings

logger = logging.getLogger(__name__)

# Registro de endpoints "daily"/periodo que aceptan rango de fechas (start_date/end_date).
# (nombre_tool, path, descripcion)
_RANGE_ENDPOINTS: list[tuple[str, str, str]] = [
    ("sleep_summary", "/usercollection/daily_sleep",
     "Resumen diario de sueno (score, contribuyentes) en un rango de fechas."),
    ("readiness_summary", "/usercollection/daily_readiness",
     "Resumen diario de readiness (disposicion) en un rango de fechas."),
    ("activity_summary", "/usercollection/daily_activity",
     "Resumen diario de actividad (pasos, calorias, MET) en un rango de fechas."),
    ("spo2_summary", "/usercollection/daily_spo2",
     "Saturacion de oxigeno (SpO2) promedio nocturna por dia."),
    ("stress_summary", "/usercollection/daily_stress",
     "Resumen diario de estres (tiempo en stress/recovery) por dia."),
    ("resilience_summary", "/usercollection/daily_resilience",
     "Resumen diario de resiliencia (nivel y contribuyentes) por dia."),
    ("cardiovascular_age", "/usercollection/daily_cardiovascular_age",
     "Edad cardiovascular estimada por dia."),
    ("sleep_periods", "/usercollection/sleep",
     "Periodos de sueno detallados: fases (REM/light/deep/awake), HR, HRV, latencia."),
    ("sleep_time", "/usercollection/sleep_time",
     "Recomendaciones de horario optimo de sueno por dia."),
    ("workouts", "/usercollection/workout",
     "Entrenamientos registrados (tipo, intensidad, calorias, distancia)."),
    ("sessions", "/usercollection/session",
     "Sesiones de momentos (meditacion, respiracion, descanso) con HR/HRV."),
    ("rest_mode_periods", "/usercollection/rest_mode_period",
     "Periodos de Rest Mode (modo descanso) activados por el usuario."),
    ("vo2_max", "/usercollection/vO2_max",
     "Mediciones de VO2 max (capacidad cardiorrespiratoria)."),
    ("enhanced_tags", "/usercollection/enhanced_tag",
     "Etiquetas mejoradas (enhanced tags) del usuario en un rango de fechas."),
    ("tags", "/usercollection/tag",
     "Etiquetas (tags) del usuario. Endpoint legado; preferir enhanced_tags."),
]


def _fmt_duration(seconds: int | float | None) -> str | None:
    """Convierte una duracion en segundos a texto legible (p.ej. '7h 12m', '38m')."""
    if seconds is None:
        return None
    total = int(seconds)
    hours, minutes = total // 3600, (total % 3600) // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def create_mcp_server(
    settings: Settings,
    store: TokenStore,
    auth: TokenVerifier | None = None,
) -> FastMCP:
    mcp = FastMCP(settings.mcp_name, auth=auth)

    # OURA_BEARER_TOKEN es un atajo de un solo usuario. Recibir un `auth` es la
    # senal de que este servidor es multiusuario (lo monta build_http_server):
    # ahi el atajo serviria los datos de salud de esa persona a cualquiera con
    # una API key valida, asi que se ignora.
    bearer_global_permitido = auth is None
    if settings.oura_bearer_token and not bearer_global_permitido:
        logger.warning(
            "OURA_BEARER_TOKEN esta configurado pero se ignora: este transporte es "
            "multiusuario y cada persona usa sus propios tokens OAuth."
        )

    async def _fetch(path: str, params: dict[str, Any] | None = None) -> Any:
        """Llama a la API de Oura con los tokens del caller actual.

        - Sin auth (stdio, un solo usuario) y con OURA_BEARER_TOKEN, lo usa.
        - En otro caso resuelve el oura_user_id del Bearer del MCP y usa los
          tokens OAuth guardados para esa persona (con refresh automatico).
        """
        if bearer_global_permitido and settings.oura_bearer_token:
            return await OuraClient(settings, settings.oura_bearer_token).get_json(path, params)
        user_id = resolve_user_id(settings)
        try:
            return await OuraClient.get_json_for_user(user_id, path, settings, store, params)
        except ValueError as exc:
            if str(exc).startswith("user_not_connected"):
                raise RuntimeError(
                    f"El usuario '{user_id}' no ha conectado su cuenta Oura. "
                    f"Abre {settings.oura_redirect_uri.rsplit('/auth/callback', 1)[0]}"
                    f"/auth/login con tu API key para autorizar el acceso."
                ) from exc
            raise

    # --- Tools generados desde el registro (rango de fechas) ---
    def _make_range_tool(path: str):
        async def _tool(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
            params = {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
            return await _fetch(path, params)
        return _tool

    for name, path, description in _RANGE_ENDPOINTS:
        fn = _make_range_tool(path)
        fn.__name__ = name
        mcp.tool(name=name, description=description)(fn)

    # --- Tools con firma propia ---
    @mcp.tool()
    async def whoami() -> dict[str, Any]:
        """Perfil del usuario Oura conectado (edad, sexo, peso, altura, email)."""
        return await _fetch("/usercollection/personal_info")

    @mcp.tool()
    async def heartrate(
        start_datetime: str | None = None, end_datetime: str | None = None
    ) -> dict[str, Any]:
        """Frecuencia cardiaca (serie temporal). Usa start_datetime/end_datetime en
        formato ISO 8601 (p.ej. 2026-06-20T00:00:00+00:00), no fechas simples."""
        params = {
            k: v
            for k, v in {"start_datetime": start_datetime, "end_datetime": end_datetime}.items()
            if v
        }
        return await _fetch("/usercollection/heartrate", params)

    @mcp.tool()
    async def sleep_last_night(day: str | None = None) -> dict[str, Any]:
        """Estadisticas detalladas del sueno principal de la noche que me levante.
        Sin argumentos usa el dia de hoy como dia de despertar; si aun no hay datos,
        cae al periodo de sueno mas reciente disponible. Pasa 'day' (YYYY-MM-DD) para
        una noche concreta. Devuelve un resumen curado (duracion, eficiencia, latencia,
        fases, HR, HRV, frecuencia respiratoria, score y contribuyentes) mas el JSON
        crudo del periodo y del daily_sleep."""
        target = date.fromisoformat(day) if day else date.today()
        # Ventana amplia para permitir fallback al periodo mas reciente <= target.
        # end_date con +1 dia porque el filtro de Oura puede excluir el borde superior.
        params = {
            "start_date": (target - timedelta(days=6)).isoformat(),
            "end_date": (target + timedelta(days=1)).isoformat(),
        }
        periods = (await _fetch("/usercollection/sleep", params)).get("data", [])
        target_iso = target.isoformat()
        # Preferir sueno principal; caer a cualquier periodo tipo "sleep" si no hay long_sleep.
        mains = [
            p for p in periods
            if p.get("type") == "long_sleep" and (p.get("day") or "") <= target_iso
        ]
        if not mains:
            mains = [
                p for p in periods
                if p.get("type") in ("long_sleep", "sleep") and (p.get("day") or "") <= target_iso
            ]
        if not mains:
            return {
                "message": f"Sin datos de sueno principal para {target_iso} ni dias previos.",
                "day": target_iso,
            }
        # Mas reciente por 'day', desempate por mayor duracion total.
        period = max(
            mains,
            key=lambda p: (p.get("day") or "", p.get("total_sleep_duration") or 0),
        )
        sleep_day = period["day"]

        # Score + contribuyentes de ese dia (endpoint distinto).
        ds = await _fetch(
            "/usercollection/daily_sleep",
            {
                "start_date": sleep_day,
                "end_date": (date.fromisoformat(sleep_day) + timedelta(days=1)).isoformat(),
            },
        )
        daily = next((d for d in ds.get("data", []) if d.get("day") == sleep_day), None)

        summary = {
            "day": sleep_day,
            "type": period.get("type"),
            "bedtime_start": period.get("bedtime_start"),
            "bedtime_end": period.get("bedtime_end"),
            "sleep_score": (daily or {}).get("score"),
            "total_sleep": _fmt_duration(period.get("total_sleep_duration")),
            "time_in_bed": _fmt_duration(period.get("time_in_bed")),
            "efficiency": period.get("efficiency"),
            "latency": _fmt_duration(period.get("latency")),
            "restless_periods": period.get("restless_periods"),
            "phases": {
                "deep": _fmt_duration(period.get("deep_sleep_duration")),
                "rem": _fmt_duration(period.get("rem_sleep_duration")),
                "light": _fmt_duration(period.get("light_sleep_duration")),
                "awake": _fmt_duration(period.get("awake_time")),
            },
            "hr": {
                "avg": period.get("average_heart_rate"),
                "lowest": period.get("lowest_heart_rate"),
            },
            "hrv_avg": period.get("average_hrv"),
            "respiratory_rate": period.get("average_breath"),
            "score_contributors": (daily or {}).get("contributors"),
        }
        return {"summary": summary, "raw": {"sleep_period": period, "daily_sleep": daily}}

    @mcp.tool()
    async def ring_configuration() -> dict[str, Any]:
        """Configuracion del anillo (modelo, color, tamano, firmware)."""
        return await _fetch("/usercollection/ring_configuration")

    @mcp.tool()
    async def health_snapshot(
        start_date: str | None = None, end_date: str | None = None
    ) -> dict[str, Any]:
        """Snapshot completo en paralelo: perfil + sueno + readiness + actividad +
        SpO2 + estres + resiliencia, para el rango indicado."""
        params = {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
        (
            profile, sleep, readiness, activity, spo2, stress, resilience
        ) = await asyncio.gather(
            _fetch("/usercollection/personal_info"),
            _fetch("/usercollection/daily_sleep", params),
            _fetch("/usercollection/daily_readiness", params),
            _fetch("/usercollection/daily_activity", params),
            _fetch("/usercollection/daily_spo2", params),
            _fetch("/usercollection/daily_stress", params),
            _fetch("/usercollection/daily_resilience", params),
        )
        return {
            "profile": profile,
            "daily_sleep": sleep,
            "daily_readiness": readiness,
            "daily_activity": activity,
            "daily_spo2": spo2,
            "daily_stress": stress,
            "daily_resilience": resilience,
        }

    # --- Webhooks (usan credenciales OAuth de cliente, no tokens de usuario) ---
    def _webhook_client() -> OuraClient:
        return OuraClient(settings, settings.oura_bearer_token or "")

    @mcp.tool()
    async def list_webhook_subscriptions() -> list[dict]:
        """Lista las suscripciones a webhooks de Oura (nivel de aplicacion)."""
        return await _webhook_client().list_webhooks()

    @mcp.tool()
    async def create_webhook_subscription(
        callback_url: str,
        verification_token: str,
        event_type: str = "update",
        data_type: str = "daily_sleep",
    ) -> dict:
        """Crea una suscripcion a webhook de Oura."""
        return await _webhook_client().create_webhook(
            callback_url, verification_token, event_type, data_type
        )

    @mcp.tool()
    async def delete_webhook_subscription(subscription_id: str) -> dict:
        """Elimina una suscripcion a webhook."""
        await _webhook_client().delete_webhook(subscription_id)
        return {"ok": True}

    @mcp.tool()
    async def renew_webhook_subscription(subscription_id: str) -> dict:
        """Renueva una suscripcion a webhook."""
        return await _webhook_client().renew_webhook(subscription_id)

    @mcp.prompt()
    def daily_checkin() -> str:
        return (
            "Resume mi estado de salud de hoy basandote en los datos de Oura: "
            "sueno, readiness, actividad, SpO2, estres y cualquier anomalia relevante."
        )

    return mcp
