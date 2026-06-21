from __future__ import annotations

import argparse
import logging

import uvicorn

from oura_mcp_server.config import get_settings
from oura_mcp_server.transports.http import create_app
from oura_mcp_server.transports.stdio import run_stdio


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="oura-mcp-server",
        description="Portable MCP server for Oura Ring",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode: stdio (default, portable) or http (OAuth callbacks + webhooks)",
    )
    parser.add_argument("--host", default=None, help="HTTP host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="HTTP port (default: 8000)")
    parser.add_argument("--log-level", default=None, help="Log level (default: INFO)")
    args = parser.parse_args()

    settings = get_settings()
    level = (args.log_level or settings.log_level).upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))

    if args.transport == "stdio":
        run_stdio(settings)
        return

    app = create_app(settings)
    uvicorn.run(
        app,
        host=args.host or settings.http_host,
        port=args.port or settings.http_port,
        log_level=level.lower(),
    )


if __name__ == "__main__":
    main()
