#!/bin/bash
set -e

JWT='eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJwYWdlcy1idWlsZC1tYWVzdHJvIiwiZXhwIjoxNzkxNTI3NjQ4LCJmZWF0dXJlcyI6WyJmaWxlcyJdLCJpYXQiOjE3OTE1MjU4NDgsImlzcyI6ImZ1bmZldHRpIiwibWF4X2ZpbGVfY291bnRfYWxsb3dlZCI6MjAwMDAsInByb2plY3ROYW1lc3BhY2UiOiJjZTdjOGIwNzMyNTc0YmQ2OWM5YjcyODk1YzZjN2FjMiJ9.RGKwzqwKuUb4OueD7h6lJnzyPSsAMcvJ2BAUzmG-WOBwR4CbKhPNCdoBi5nqwTxEsGB8lPlNx55j0q137xrVG8QBfOMAKkkbVuOYC2pXLNxqSh5Rc4QsPJypiX1eiwLx_8Y88pTQ9QsMyusv-4X29CIh9A3sXn86ggk2j7q4fNwXfjzIewbVY5JhR-T8Rf21WVQQ5FY0DRjjcMMdN8yFZXN9PLJjoZjeD67mESXXxFoEGfQRGUvZa8G641Tr6WCxfaQ_D9IuYk6zwKXuv4l0DebSPspOmKJRiXVmN9y5tEXXwaObTmvJZs_55w1cHP-KxRTldneC9DBg26uis3YZKN8utDUC4zHNwqXBk9wLXNDMQgu1W78tPJfG136fsqW3pGgkUocog45z0OT0zg6NhxEkJi_-vqI1DnlQGVDIRRlk5JpEDGtXoMIkcvB8seYJ-Nnkiq_Kr1GoQONTYWPk3k5ES8D_hbVwI1hCrUnPGZUgPgyr5cXdOBRq_hyJEk-fANPDchn0GSSn5xWxUuAPv1T991yroRSd1bYpVQ1nH2mCUuGY6XCxCv2g9G7d7dooRzk_YRh0a8kavhaxUwii527GRcf6UPnx8rqM-wnhwaoyPs_VZDCKa_nc5I7fBFCiXHsShEte1l02Do9KQ7pVnvcD7ouTtSz46F7xFJgqU_A'
ACCOUNT_ID='2450b16d188a6686db33d4e1b31aff1a'
PROJECT='java-sql-ai-tutorial'
SITE_DIR='/workspace/site'
API='https://api.cloudflare.com/client/v4'
UPLOAD_URL="${API}/pages/assets/upload"
DEPLOY_URL="${API}/accounts/${ACCOUNT_ID}/pages/projects/${PROJECT}/deployments"

echo "== Step 1: Generate manifest and upload assets =="
MANIFEST='{}'
ASSETS_JSON='[]'

for f in $(find "$SITE_DIR" -type f | sort); do
  rel="${f#$SITE_DIR/}"
  logical="/$rel"
  hash=$(sha256sum "$f" | cut -d' ' -f1)
  b64=$(base64 -w0 "$f")
  
  # Determine content type
  ct="application/octet-stream"
  case "$rel" in
    *.html) ct="text/html" ;;
    *.css)  ct="text/css" ;;
    *.js)   ct="application/javascript" ;;
    *.json) ct="application/json" ;;
    *.png)  ct="image/png" ;;
    *.svg)  ct="image/svg+xml" ;;
  esac
  
  # Build asset JSON
  ASSET="{\"key\":\"$hash\",\"value\":\"$b64\",\"base64\":true,\"metadata\":{\"contentType\":\"$ct\"}}"
  
  # Add to manifest (using python for JSON manipulation)
  MANIFEST=$(python3 -c "
import json
m = json.loads('$MANIFEST')
m['$logical'] = '$hash'
print(json.dumps(m))
")
  
  ASSETS_JSON=$(python3 -c "
import json
a = json.loads('$ASSETS_JSON')
a.append(json.loads('$ASSET'))
print(json.dumps(a))
")
  
  echo "  $logical  ${hash:0:12}...  $(echo $b64 | wc -c) b64"
done

echo ""
echo "== Step 2: Upload assets in batches =="
# Split into batches of ~200KB and upload
python3 -c "
import json, sys, subprocess, os

assets = json.loads('$ASSETS_JSON')
MAX = 200 * 1024
batch, batch_size = [], 0
batches = []
for a in assets:
    sz = len(a['value'])
    if batch and batch_size + sz > MAX:
        batches.append(batch); batch, batch_size = [], 0
    batch.append(a); batch_size += sz
if batch:
    batches.append(batch)

jwt = '$JWT'
upload_url = '$UPLOAD_URL'

for i, b in enumerate(batches):
    payload = json.dumps(b)
    # Write payload to temp file
    with open('/tmp/batch_payload.json', 'w') as f:
        f.write(payload)
    result = subprocess.run([
        'curl', '-s', '-X', 'POST', upload_url,
        '-H', f'Authorization: Bearer {jwt}',
        '-H', 'Content-Type: application/json',
        '-d', f'@/tmp/batch_payload.json'
    ], capture_output=True, text=True)
    try:
        r = json.loads(result.stdout)
        ok = r.get('success', False)
        print(f'  batch {i+1}/{len(batches)}: {\"OK\" if ok else \"FAIL\"} - {result.stdout[:200]}')
        if not ok:
            sys.exit(1)
    except:
        print(f'  batch {i+1}/{len(batches)}: PARSE ERROR - {result.stdout[:200]}')
        sys.exit(1)
os.unlink('/tmp/batch_payload.json')
"

echo ""
echo "== Step 3: Save manifest =="
echo "$MANIFEST" | python3 -m json.tool > /workspace/cf_manifest_final.json
echo "Saved to /workspace/cf_manifest_final.json"

echo ""
echo "== Step 4: Create deployment =="
MANIFEST_JSON=$(echo "$MANIFEST" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)))")
BOUNDARY="----PagesDeploy$(date +%s)"

# Build multipart body
BODY_FILE="/tmp/deploy_body.txt"
python3 -c "
import json
manifest = json.loads('$MANIFEST')
boundary = '$BOUNDARY'
body = f'--{boundary}\r\n'
body += 'Content-Disposition: form-data; name=\"manifest\"\r\n'
body += 'Content-Type: application/json\r\n\r\n'
body += json.dumps(manifest) + '\r\n'
body += f'--{boundary}--\r\n'
with open('$BODY_FILE', 'w') as f:
    f.write(body)
"

RESULT=$(curl -s -X POST "$DEPLOY_URL" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: multipart/form-data; boundary=$BOUNDARY" \
  -d "@$BODY_FILE")

echo "$RESULT" | python3 -c "
import json, sys
try:
    r = json.load(sys.stdin)
    if r.get('success'):
        dep = r.get('result', {})
        print(f'  DEPLOYED: {dep.get(\"url\")}')
        print(f'  id: {dep.get(\"id\")}')
        print(f'  stage: {dep.get(\"latest_stage\", {}).get(\"name\")} - {dep.get(\"latest_stage\", {}).get(\"status\")}')
    else:
        print(f'  FAILED: {r.get(\"errors\")}')
        sys.exit(1)
except Exception as e:
    print(f'  ERROR: {e}')
    sys.exit(1)
"

rm -f "$BODY_FILE"
