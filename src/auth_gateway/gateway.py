from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
import httpx
import os
import secrets
from loguru import logger


app = FastAPI(title="Okta MCP Auth Gateway")


# Session management
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET", secrets.token_hex(32)),
    max_age=3600 * 8  # 8 hour sessions
)


# Okta OAuth setup
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


def get_mcp_url_for_user(user: dict) -> tuple[str, str]:
    """Determine which MCP server to use based on user's groups"""
    admin_group = os.getenv("ADMIN_GROUP_NAME", "Okta-MCP-Admins")
    user_groups = user.get('groups', [])
    
    if admin_group in user_groups:
        logger.info(f"User {user['email']} has admin access")
        return os.getenv("MCP_ADMIN_URL"), "admin"
    else:
        logger.info(f"User {user['email']} has read-only access")
        return os.getenv("MCP_READONLY_URL"), "readonly"


@app.get("/")
async def root(request: Request):
    user = request.session.get('user')
    if user:
        _, access_level = get_mcp_url_for_user(user)
        return {
            "status": "authenticated",
            "user": user['email'],
            "access_level": access_level,
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
        user_info = token.get('userinfo')
        
        logger.info(f"User authenticated: {user_info.get('email')}")
        
        request.session['user'] = {
            'sub': user_info['sub'],
            'email': user_info['email'],
            'name': user_info.get('name'),
            'groups': user_info.get('groups', [])
        }
        
        _, access_level = get_mcp_url_for_user(request.session['user'])
        
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
    request.session.clear()
    return {"status": "logged out"}


async def get_current_user(request: Request):
    """Get user from session OR from StrongDM headers"""
    
    # Option 1: Check for existing session (browser OAuth)
    user = request.session.get('user')
    if user:
        logger.info(f"User authenticated via session: {user['email']}")
        return user
    
    # Option 2: Check for StrongDM user headers (for SSE clients)
    sdm_email = request.headers.get("X-SDM-User-Email")
    sdm_groups = request.headers.get("X-SDM-User-Groups")
    
    if sdm_email:
        # User authenticated via StrongDM
        logger.info(f"User authenticated via StrongDM: {sdm_email}")
        
        # Parse groups from comma-separated string
        groups = sdm_groups.split(",") if sdm_groups else []
        
        return {
            'sub': sdm_email,  # Use email as sub
            'email': sdm_email,
            'name': sdm_email.split('@')[0],
            'groups': groups
        }
    
    # Option 3: Development/testing bypass
    if os.getenv("GATEWAY_DEV_MODE") == "true":
        logger.warning("DEV MODE: Using test user")
        return {
            'sub': 'test@kaltura.com',
            'email': 'test@kaltura.com',
            'name': 'Test User',
            'groups': [os.getenv("ADMIN_GROUP_NAME", "Okta-MCP-Admins")]
        }
    
    # No authentication found
    raise HTTPException(
        status_code=401,
        detail="Not authenticated. Visit /login to authenticate or ensure StrongDM headers are present."
    )


@app.get("/sse")
async def mcp_sse_endpoint(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """SSE endpoint - routes to appropriate MCP server based on user permissions"""
    mcp_url, access_level = get_mcp_url_for_user(user)
    logger.info(f"[{user['email']}] SSE connection ({access_level}) -> {mcp_url}")
    
    # Stream from internal MCP server
    async def stream_from_mcp():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "GET",
                f"{mcp_url}/sse",
                headers={
                    "X-User-Email": user['email'],
                    "X-User-ID": user['sub'],
                    "X-User-Groups": ",".join(user.get('groups', [])),
                    "X-Access-Level": access_level,
                    "X-Internal-Auth": os.getenv("INTERNAL_AUTH_TOKEN", "")
                }
            ) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
    
    return StreamingResponse(
        stream_from_mcp(),
        media_type="text/event-stream"
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "okta-mcp-auth-gateway"}


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Okta MCP Auth Gateway")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.getenv("GATEWAY_PORT", "9000"))
    )
