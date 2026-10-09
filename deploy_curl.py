#!/usr/bin/env python3
"""
Deploy /workspace/site to Cloudflare Pages using curl for HTTP calls
(urllib fails auth through proxy, but curl works).
"""
import os, sys, json, hashlib, base64, mimetypes, subprocess, tempfile

JWT = os.environ.get("CF_JWT", "").strip()
if not JWT:
    sys.exit("Please set CF_JWT env var")

ACCOUNT_ID = "2450b16d188a6686db33d4e1b31aff1a"
PROJECT = "java-sql-ai-tutorial"
SITE_DIR = "/workspace/site"
API = "https://api.cloudflare.com/client/v4"
UPLOAD_URL = f"{API}/pages/assets/upload"
DEPLOY_URL = f"{API}/accounts/{ACCOUNT_ID}/pages/projects/{PROJECT}/deployments"

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def curl_post(url, json_data=None, bearer=None, multipart_body=None, content_type="application/json"):
    """Use curl for HTTP calls since urllib has proxy auth issues."""
    cmd = ["curl", "-s", "-X", "POST", url]
    if bearer:
        cmd += ["-H", f"Authorization: Bearer {bearer}"]
    cmd += ["-H", f"Content-Type: {content_type}"]
    
    if json_data is not None:
        # Write to temp file to avoid shell escaping issues
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json.dumps(json_data))
            tmp = f.name
        cmd += ["-d", f"@{tmp}"]
    
    if multipart_body is not None:
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.body', delete=False) as f:
            f.write(multipart_body)
            tmp = f.name
        cmd += ["-d", f"@{tmp}"]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    try:
        os.unlink(tmp)
    except:
        pass
    return result.stdout

def main():
    print("== Step 1: collect files ==")
    assets = []
    manifest = {}
    for root, _, files in os.walk(SITE_DIR):
        for fn in sorted(files):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, SITE_DIR).replace(os.sep, "/")
            logical = "/" + rel
            h = sha256_file(full)
            with open(full, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            ct, _ = mimetypes.guess_type(full)
            assets.append({"key": h, "value": b64, "base64": True,
                           "metadata": {"contentType": ct or "application/octet-stream"}})
            manifest[logical] = h
            print(f"  {logical:30s}  {h[:12]}…  {len(b64):>8d} b64")

    print(f"\n== Step 2: upload {len(assets)} assets in batches ==")
    MAX = 200 * 1024
    batch, batch_size = [], 0
    batches = []
    for a in assets:
        sz = len(a["value"])
        if batch and batch_size + sz > MAX:
            batches.append(batch); batch, batch_size = [], 0
        batch.append(a); batch_size += sz
    if batch:
        batches.append(batch)

    print(f"  {len(batches)} batch(es) to upload")
    for i, b in enumerate(batches):
        resp = curl_post(UPLOAD_URL, json_data=b, bearer=JWT)
        try:
            r = json.loads(resp)
            ok = r.get("success", False)
            sc = r.get("result", {}).get("successful_key_count", 0)
            print(f"  batch {i+1}/{len(batches)}: {'OK' if ok else 'FAIL'} - {sc} keys uploaded")
            if not ok:
                print(f"    errors: {r.get('errors')}")
                sys.exit(f"upload batch {i+1} failed")
        except Exception as e:
            print(f"  batch {i+1}/{len(batches)}: PARSE ERROR: {e}")
            print(f"    response: {resp[:300]}")
            sys.exit(1)

    print("\n== Step 3: upsert hashes ==")
    all_hashes = list(manifest.values())
    resp = curl_post(f"{API}/pages/assets/upsert-hashes", json_data={"hashes": all_hashes}, bearer=JWT)
    try:
        r = json.loads(resp)
        print(f"  upsert: {'OK' if r.get('success') else 'FAIL'} - {resp[:200]}")
        if not r.get("success"):
            sys.exit("upsert-hashes failed")
    except:
        print(f"  upsert response: {resp[:300]}")
        sys.exit("upsert-hashes parse error")

    print("\n== Step 4: create deployment ==")
    boundary = "----PagesDeploy" + os.urandom(8).hex()
    manifest_json = json.dumps(manifest)
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="manifest"\r\n'
        "Content-Type: application/json\r\n\r\n"
        f"{manifest_json}\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    resp = curl_post(DEPLOY_URL, multipart_body=body, bearer=JWT,
                     content_type=f"multipart/form-data; boundary={boundary}")
    try:
        r = json.loads(resp)
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
        print(f"  response: {resp[:500]}")
        sys.exit(1)

if __name__ == "__main__":
    main()
