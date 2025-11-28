# Docker Containerisation Instructions
Pulling the Image
Pull the latest image from Docker Hub:

bash
docker pull blackstaa/okta-mcp-server:dev

Basic Usage
Run the container with required environment variables:

bash
docker run --rm -i \
  -e OKTA_API_BASE_URL="https://your-org.okta.com" \
  -e OKTA_API_TOKEN="your_api_token_here" \
  blackstaa/okta-mcp-server:dev

Environment Variables
Variable	Required	Description	Example
OKTA_API_BASE_URL	Yes	Your Okta organization URL	https://dev-12345.okta.com
OKTA_API_TOKEN	Yes	Your Okta API token	00abc...
OKTA_LOG_LEVEL	No	Logging level (default: INFO)	DEBUG, INFO, WARNING, ERROR
OKTA_LOG_FILE	No	Path to log file (optional)	/tmp/okta-mcp.log

Testing the Container
Test that the container can connect to Okta's API:

bash
docker run --rm blackstaa/okta-mcp-server:dev \
  python -c "
import urllib.request
url = 'https://your-org.okta.com/api/v1/users?limit=1'
headers = {'Authorization': 'SSWS your_api_token_here', 'Accept': 'application/json'}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as response:
    print('Status:', response.status)
"