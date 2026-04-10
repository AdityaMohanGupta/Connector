from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.mcp_server import build_mcp_server
from app.routes import agent, auth, outlook

settings = get_settings()

app = FastAPI(title="Outlook Connector API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.resolved_frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def protect_mcp(request: Request, call_next: Callable):
    if request.url.path.startswith("/mcp"):
        if not settings.mcp_bearer_token:
            return JSONResponse(
                status_code=503,
                content={"detail": "MCP_BEARER_TOKEN is blank. Fill backend/.env before using /mcp."},
            )
        expected = f"Bearer {settings.mcp_bearer_token}"
        if request.headers.get("authorization") != expected:
            return JSONResponse(status_code=401, content={"detail": "Invalid MCP bearer token."})
    return await call_next(request)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(outlook.router)
app.include_router(agent.router)

mcp_server = build_mcp_server()
if mcp_server is not None:
    app.mount("/mcp", mcp_server.streamable_http_app())
