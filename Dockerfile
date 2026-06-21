# Oura MCP Server — imagen para el host multi-MCP de Scaleflow.
FROM python:3.12-slim

WORKDIR /app

# Instala el paquete (es instalable: tiene build-system + layout src/).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Transporte HTTP: protocolo MCP en /mcp + rutas OAuth en el mismo puerto.
ENV TRANSPORT=http \
    HTTP_HOST=0.0.0.0 \
    HTTP_PORT=8000 \
    TOKEN_DB_PATH=/app/data/tokens.sqlite3 \
    TENANTS_CONFIG_PATH=/app/config/tenants.yaml

EXPOSE 8000

CMD ["python", "-m", "oura_mcp_server", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
