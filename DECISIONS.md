# Decisiones de arquitectura

## 1. Separacion core / transporte
Se separo la logica MCP del transporte para que el servidor sea portable
a cualquier cliente MCP (Claude Desktop, Cursor, VS Code, etc.).

## 2. stdio como default
Se eligio stdio como transporte por defecto porque es el estandar MCP
y cualquier agente/cliente MCP lo soporta.

## 3. Auth dual
- **Modo principal**: OAuth2 authorization code + refresh token (produccion)
- **Modo fallback**: bearer token directo en variable de entorno (solo dev)
  Los PATs de Oura fueron deprecados en dic 2025. Los tokens directos
  expiran a los 30 dias.

## 4. SQLite persistente
Base de datos local y portable sin dependencias externas.

## 5. HTTP separado
FastAPI queda aislado para callback OAuth, healthcheck y webhooks.
No se mezcla con el transporte MCP stdio.

## 6. Multiples herramientas
Se mantienen las tools de webhooks (list, create, renew, delete) y
el health snapshot unificado.
