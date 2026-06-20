from fastapi import FastAPI

from .api import router

app = FastAPI(title="Oura MCP Server", version="0.2.0")
app.include_router(router)
