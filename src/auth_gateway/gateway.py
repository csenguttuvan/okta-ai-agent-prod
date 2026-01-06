import os
from fastapi import FastAPI, Request, Depends, HTTPException
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
import httpx
from loguru import logger

app = FastAPI(title="Okta MCP Auth Gateway")

app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET"),
    max_age=3600 * 8
)

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
            "access_level": access_level
        }
    return {"status": "unauthenticated", "login_url": "/login"}

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
        
        return {
            "status": "success",
            "message": "Authenticated successfully",
            "user": user_info['email'],
            "access_level": access_level
        }
        
    except Exception as e:
        logger.error(f"Auth callback error: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"status": "logged out"}

async def get_current_user(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="Not authenticated. Visit /login to authenticate."
        )
    return user

@app.get("/sse")
async def mcp_sse_endpoint(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """SSE endpoint - routes to appropriate MCP server"""
    mcp_url, access_level = get_mcp_url_for_user(user)
    logger.info(f"[{user['email']}] SSE connection ({access_level}) -> {mcp_url}")
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET",
            f"{mcp_url}/sse",
            headers={
                "X-User-Email": user['email'],
                "X-User-ID": user['sub'],
                "X-User-Groups": ",".join(user.get('groups', [])),
                "X-Access-Level": access_level,
                "X-Internal-Auth": os.getenv("INTERNAL_AUTH_TOKEN")
            },
            timeout=None
        ) as response:
            async for chunk in response.aiter_bytes():
                yield chunk

@app.post("/mcp/call")
async def mcp_call_proxy(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Proxy MCP tool calls to appropriate server"""
    body = await request.json()
    mcp_url, access_level = get_mcp_url_for_user(user)
    
    logger.info(f"[{user['email']}] ({access_level}) MCP call: {body.get('method', 'unknown')}")
    
    if 'params' not in body:
        body['params'] = {}
    if 'meta' not in body['params']:
        body['params']['meta'] = {}
    
    body['params']['meta'].update({
        'user_email': user['email'],
        'user_id': user['sub'],
        'user_name': user.get('name'),
        'groups': user.get('groups', []),
        'access_level': access_level
    })
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{mcp_url}/mcp/call",
            json=body,
            headers={
                "X-User-Email": user['email'],
                "X-Access-Level": access_level,
                "X-Internal-Auth": os.getenv("INTERNAL_AUTH_TOKEN")
            },
            timeout=60.0
        )
        return response.json()

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "okta-mcp-auth-gateway"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Okta MCP Auth Gateway with role-based routing")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("GATEWAY_PORT", "9000")))
