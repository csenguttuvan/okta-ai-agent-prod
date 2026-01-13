from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, Response
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
import httpx
import os
import secrets
import uuid
from loguru import logger
from typing import Dict


app = FastAPI(title="Okta MCP Auth Gateway")


# -------------------------
# Session management
# -------------------------
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", secrets.token_hex(32)),
    max_age=3600 * 8  # 8 hour sessions
)


# ✅ Track active MCP sessions per user
active_mcp_sessions: Dict[str, str] = {}


# -------------------------
# Okta OAuth setup
# -------------------------
oauth = OAuth()
oauth.register(
    name='okta',
    client_id=os.getenv("OKTA_CLIENT_ID"),
    server_metadata_url=f'{os.getenv("OKTA_ISSUER")}/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid profile email groups',
        'code_challenge_method': 'S256'
    }
)


# -------------------------
# Helper functions
# -------------------------
def get_mcp_url() -> str:
    mcp_url = os.getenv("MCP_ADMIN_URL") or os.getenv("MCP_READONLY_URL") or os.getenv("MCP_URL")
    if not mcp_url:
        raise ValueError("No MCP URL configured (MCP_ADMIN_URL or MCP_READONLY_URL)")
    return mcp_url

def get_access_level() -> str:
    # Explicit env var beats guessing
    level = os.getenv("ACCESS_LEVEL")
    if level in ("admin", "readonly"):
        return level

    # Fallback: infer by which env var is set (reliable)
    if os.getenv("MCP_ADMIN_URL"):
        return "admin"
    if os.getenv("MCP_READONLY_URL"):
        return "readonly"

    return "readonly"


# -------------------------
# Routes
# -------------------------
@app.get("/")
async def root(request: Request):
    user = request.session.get('user')
    mcp_url = get_mcp_url()
    access_level = get_access_level()
    
    if user:
        return {
            "status": "authenticated",
            "user": user['email'],
            "access_level": access_level,
            "mcp_url": mcp_url,
            "message": "Gateway is running. Connect your MCP client to /sse"
        }

    return {
        "status": "unauthenticated",
        "message": "Visit /login to authenticate",
        "login_url": "/login"
    }


@app.get("/login")
async def login(request: Request):
    redirect_uri = os.getenv("REDIRECT_URI", str(request.url_for('auth_callback')))
    logger.info(f"Initiating login, redirect_uri={redirect_uri}")
    return await oauth.okta.authorize_redirect(request, redirect_uri)


@app.get("/oauth/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.okta.authorize_access_token(request)
        user_info = token.get('userinfo', {})
        logger.info(f"User authenticated: {user_info.get('email')}")

        request.session['user'] = {
            'sub': user_info['sub'],
            'email': user_info['email'],
            'name': user_info.get('name'),
            'groups': user_info.get('groups', [])
        }

        mcp_url = get_mcp_url()
        access_level = get_access_level()

        return JSONResponse({
            "status": "success",
            "message": "Authenticated successfully! You can now use your MCP client.",
            "user": user_info['email'],
            "access_level": access_level
        })

    except Exception as e:
        logger.error(f"Auth callback error: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@app.get("/logout")
async def logout(request: Request):
    user = request.session.get('user')
    if user and user['email'] in active_mcp_sessions:
        del active_mcp_sessions[user['email']]  # ✅ Clean up session
    request.session.clear()
    return {"status": "logged out"}


# -------------------------
# Authentication dependency
# -------------------------
async def get_current_user(request: Request):
    """Get user from session OR StrongDM headers"""
    # Option 1: Check session (browser OAuth)
    user = request.session.get('user')
    if user:
        logger.info(f"User authenticated via session: {user['email']}")
        return user

    # Option 2: StrongDM headers (SSE clients)
    sdm_email = request.headers.get("X-Forwarded-User")
    if sdm_email:
        logger.info(f"User authenticated via StrongDM: {sdm_email}")
        return {
            'sub': sdm_email,
            'email': sdm_email,
            'name': sdm_email.split('@')[0],
            'groups': ["Okta Administrators"]
        }

    # Option 3: Dev mode
    if os.getenv("GATEWAY_DEV_MODE") == "true":
        logger.warning("DEV MODE: Using test user")
        return {
            'sub': 'test@kaltura.com',
            'email': 'test@kaltura.com',
            'name': 'Test User',
            'groups': []
        }

    # No authentication
    raise HTTPException(
        status_code=401,
        detail="Not authenticated. Visit /login or ensure StrongDM headers are present."
    )


# -------------------------
# SSE endpoint
# -------------------------
@app.get("/sse")
async def mcp_sse_endpoint(request: Request, current_user: dict = Depends(get_current_user)):
    email = current_user["email"]
    mcp_url = get_mcp_url()
    
    # ✅ Add /sse to the base URL
    mcp_sse_url = f"{mcp_url}/sse"
    
    logger.info(f"[{email}] SSE connection -> {mcp_sse_url}")
    
    async def stream_from_mcp():
        headers = {
            "Authorization": f"Bearer {os.getenv('INTERNAL_AUTH_TOKEN')}",
            "Accept": "text/event-stream",
        }
        
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", mcp_sse_url, headers=headers) as response:  # ✅ Use mcp_sse_url
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
    
    return StreamingResponse(
        stream_from_mcp(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# -------------------------
# Proxy POST messages
# -------------------------
@app.post("/messages/")
async def proxy_messages(request: Request, user: dict = Depends(get_current_user)):
    """Proxy messages to backend MCP server"""
    mcp_url = get_mcp_url()
    access_level = get_access_level()
    
    logger.info(f"[{user['email']}] POST /messages/ ({access_level}) -> {mcp_url}")

    body = await request.body()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{mcp_url}/messages/",
                content=body,
                params=dict(request.query_params),
                headers={
                    "X-User-Email": user['email'],
                    "X-User-ID": user['sub'],
                    "X-User-Groups": ",".join(user.get('groups', [])),
                    "X-Access-Level": access_level,
                    "Content-Type": request.headers.get("content-type", "application/json"),
                    "X-Internal-Auth": os.getenv("INTERNAL_AUTH_TOKEN", "")
                }
            )

            logger.info(f"Backend response status: {response.status_code}")

            if response.status_code == 202:
                return Response(status_code=202)

            if response.text:
                try:
                    content = response.json()
                    return JSONResponse(content=content, status_code=response.status_code)
                except Exception:
                    return Response(content=response.text, status_code=response.status_code)
            else:
                return Response(status_code=response.status_code)

        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to MCP server at {mcp_url}: {e}")
            raise HTTPException(status_code=503, detail=f"MCP server unavailable: {str(e)}")
        except Exception as e:
            logger.error(f"Error proxying message: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Health check
# -------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "okta-mcp-auth-gateway"}


@app.head("/health")
async def health_head():
    return Response(status_code=200)


# -------------------------
# Startup for local run
# -------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Okta MCP Auth Gateway")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("GATEWAY_PORT", "9000"))
    )
