import asyncio
import os

# Set environment
os.environ["OKTA_API_BASE_URL"] = "https://integrator-7772662.okta.com"
os.environ["OKTA_CLIENT_ID"] = "0oay0b661jlQnwFJG697"
os.environ["OKTA_PRIVATE_KEY_PATH"] = "/Users/chrissenguttuvan/Desktop/okta-ai-agent/okta-mcp-server/keys/private_key.pem"
os.environ["OKTA_SCOPES"] = "okta.users.read okta.groups.read okta.apps.read okta.logs.read"
os.environ["OKTA_LOG_LEVEL"] = "DEBUG"

from okta_mcp_server.oauth_jwt_client import init_okta_client, get_client

async def test_users():
    """Test listing users"""
    print("Initializing OAuth client...")
    init_okta_client()
    
    print("\nTesting raw API call...")
    client = get_client()
    
    # Raw API call
    response = await client.get("/api/v1/users", params={"limit": 10})
    
    print(f"\nResponse type: {type(response)}")
    print(f"Response content: {response}")
    
    if isinstance(response, list):
        print(f"\n✅ Found {len(response)} users")
        for user in response[:3]:
            print(f"  - {user.get('profile', {}).get('email', 'N/A')}")
    else:
        print(f"\n❌ Unexpected response format")
        print(f"Keys: {response.keys() if hasattr(response, 'keys') else 'Not a dict'}")

if __name__ == "__main__":
    asyncio.run(test_users())
