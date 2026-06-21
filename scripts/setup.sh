#!/usr/bin/env bash
set -euo pipefail

echo "==> Instalando oura-mcp-server..."
python -m pip install -U pip
python -m pip install -e ".[dev]"

echo ""
echo "==> OK"
echo "    Modo stdio (portable, default):"
echo "        python -m oura_mcp_server"
echo ""
echo "    Modo HTTP (OAuth + webhooks):"
echo "        python -m oura_mcp_server --transport http"
echo ""
echo "    Tests:"
echo "        pytest -v"
