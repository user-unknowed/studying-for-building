#!/usr/bin/env python3
"""Just Step 4: create deployment using curl -F for proper multipart."""
import os, sys, json, subprocess, tempfile

JWT = os.environ["CF_JWT"]
ACCOUNT_ID = "2450b16d188a6686db33d4e1b31aff1a"
PROJECT = "java-sql-ai-tutorial"
DEPLOY_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/pages/projects/{PROJECT}/deployments"

# Load manifest
with open("/workspace/cf_manifest.json") as f:
    manifest = json.load(f)

print(f"Manifest has {len(manifest)} entries")

# Write manifest to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(manifest, f)
    manifest_file = f.name

# Use curl -F for proper multipart form data
cmd = [
    "curl", "-s", "-X", "POST", DEPLOY_URL,
    "-H", f"Authorization: Bearer {JWT}",
    "-F", f"manifest=<{manifest_file};type=application/json",
]

print(f"Running: curl -X POST {DEPLOY_URL} ...")
result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
os.unlink(manifest_file)

try:
    r = json.loads(result.stdout)
    if r.get("success"):
        dep = r.get("result", {})
        print(f"\n  DEPLOYED: {dep.get('url')}")
        print(f"  id: {dep.get('id')}")
        print(f"  stage: {dep.get('latest_stage', {}).get('name')} - {dep.get('latest_stage', {}).get('status')}")
        print(f"  live: https://{PROJECT}.pages.dev")
        print(f"  aliases: {dep.get('aliases')}")
    else:
        print(f"  FAILED: {r.get('errors')}")
        sys.exit(1)
except Exception as e:
    print(f"  ERROR: {e}")
    print(f"  stdout: {result.stdout[:500]}")
    print(f"  stderr: {result.stderr[:500]}")
    sys.exit(1)
