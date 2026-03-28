import jwt, time, requests, argparse, sys

parser = argparse.ArgumentParser()
parser.add_argument('--app-id')
parser.add_argument('--private-key')
parser.add_argument('--installation-id')
args = parser.parse_args()

# Step 1 — Generate JWT
payload = {
    'iat': int(time.time()) - 60,
    'exp': int(time.time()) + 540,
    'iss': args.app_id
}
jwt_token = jwt.encode(payload, args.private_key, algorithm='RS256')

# Step 2 — Exchange JWT for installation access token
resp = requests.post(
    f"https://api.github.com/app/installations/{args.installation_id}/access_tokens",
    headers={
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github+json'
    }
)
if resp.status_code != 201:
    print(f"ERROR getting installation token: {resp.status_code} {resp.text}", file=sys.stderr)
    sys.exit(1)

installation_token = resp.json()['token']

# Step 3 — Exchange installation token for runner registration token
resp2 = requests.post(
    "https://api.github.com/repos/csenguttuvan/okta-ai-agent-prod/actions/runners/registration-token",
    headers={
        'Authorization': f'Bearer {installation_token}',
        'Accept': 'application/vnd.github+json'
    }
)
if resp2.status_code != 201:
    print(f"ERROR getting runner token: {resp2.status_code} {resp2.text}", file=sys.stderr)
    sys.exit(1)

# Print the actual runner registration token
print(resp2.json()['token'])