#!/usr/bin/env python3
"""
Deploy /workspace/site to Cloudflare Pages using a JWT (obtained via MCP tool).

Key fixes based on Cloudflare OpenAPI spec:
- Upload URL: POST /pages/assets/upload (NO account_id prefix)
- Asset format: {base64, key, metadata:{contentType}, value}  (metadata nested!)
- Deployment manifest: {"/index.html": "hash"} with leading slash (wrangler convention)
"""
import os, sys, json, hashlib, base64, mimetypes, urllib.request, urllib.error

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

def http_call(url, method="GET", data=None, headers=None):
    req = urllib.request.Request(url, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data is not None:
        if isinstance(data, str):
            data = data.encode()
        req.data = data
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)

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
            # Use metadata.contentType per OpenAPI spec
            assets.append({"key": h, "value": b64, "base64": True,
                           "metadata": {"contentType": ct or "application/octet-stream"}})
            manifest[logical] = h
            print(f"  {logical:30s}  {h[:12]}…  {len(b64):>8d} b64")

    print(f"\n== Step 2: upload {len(assets)} assets in batches ==")
    MAX = 200 * 1024  # 200KB per batch
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
        payload = json.dumps(b)
        status, body = http_call(UPLOAD_URL, method="POST", data=payload, headers={
            "Authorization": f"Bearer {JWT}",
            "Content-Type": "application/json",
        })
        ok = (200 <= status < 300)
        print(f"  batch {i+1}/{len(batches)}: HTTP {status} ({len(payload)} bytes) {'OK' if ok else 'FAIL'}")
        print(f"    response: {body[:400]}")
        if not ok:
            sys.exit(f"upload batch {i+1} failed")
        try:
            r = json.loads(body)
            if not r.get("success"):
                print(f"    API error: {r.get('errors')}")
                sys.exit(1)
        except Exception:
            pass

    if os.environ.get("SKIP_UPLOAD_ONLY"):
        print("\n== SKIP_UPLOAD_ONLY: upload done, exiting ==")
        return

    print("\n== Step 2b: upsert hashes (register assets) ==")
    all_hashes = list(manifest.values())
    status, body = http_call(f"{API}/pages/assets/upsert-hashes", method="POST",
                            data=json.dumps({"hashes": all_hashes}),
                            headers={"Authorization": f"Bearer {JWT}",
                                     "Content-Type": "application/json"})
    print(f"  upsert-hashes: HTTP {status}")
    print(f"    response: {body[:400]}")
    if not (200 <= status < 300):
        sys.exit("upsert-hashes failed")

    if os.environ.get("SKIP_DEPLOY"):
        print("\n== SKIP_DEPLOY set, saving manifest and exiting ==")
        with open("/workspace/cf_manifest.json", "w") as f:
            json.dump(manifest, f, indent=0)
        return

    print("\n== Step 3: create deployment with manifest ==")
    boundary = "----PagesDeploy" + os.urandom(8).hex()
    manifest_json = json.dumps(manifest)
    body_parts = []
    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(b'Content-Disposition: form-data; name="manifest"\r\n')
    body_parts.append(b"Content-Type: application/json\r\n\r\n")
    body_parts.append(manifest_json.encode())
    body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(body_parts)

    status, resp_body = http_call(DEPLOY_URL, method="POST", data=body, headers={
        "Authorization": f"Bearer {JWT}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
    print(f"  deployment: HTTP {status}")
    if 200 <= status < 300:
        try:
            r = json.loads(resp_body)
            dep = r.get("result", {})
            print(f"\n  DEPLOYED: {dep.get('url')}")
            print(f"  id: {dep.get('id')}")
            print(f"  live: https://{PROJECT}.pages.dev")
            print(f"  aliases: {dep.get('aliases')}")
        except Exception as e:
            print(f"  (parse error: {e}) {resp_body[:500]}")
    else:
        print(f"  FAILED: {resp_body[:1200]}")
        sys.exit(1)

if __name__ == "__main__":
    main()
