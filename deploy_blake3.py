#!/usr/bin/env python3
"""
Deploy /workspace/site to Cloudflare Pages using BLAKE3 hashes.

Steps:
1. Load BLAKE3 manifest from blake3_manifest.json (computed by compute_blake3.js)
2. Upload assets in batches (POST /pages/assets/upload with JWT)
3. Create deployment with manifest (POST /accounts/{id}/pages/projects/{name}/deployments)
"""
import os, sys, json, base64, mimetypes, urllib.request, urllib.error

# Load JWT from env or file
JWT = os.environ.get("CF_JWT", "").strip()
if not JWT:
    jwt_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cf_jwt")
    if os.path.exists(jwt_file):
        with open(jwt_file) as f:
            JWT = f.read().strip()
if not JWT:
    sys.exit("ERROR: Please set CF_JWT env var or create .cf_jwt file")

ACCOUNT_ID = "2450b16d188a6686db33d4e1b31aff1a"
PROJECT = "java-sql-ai-tutorial"
SITE_DIR = "/workspace/site"
MANIFEST_FILE = "/workspace/blake3_manifest.json"
API = "https://api.cloudflare.com/client/v4"
UPLOAD_URL = f"{API}/pages/assets/upload"
DEPLOY_URL = f"{API}/accounts/{ACCOUNT_ID}/pages/projects/{PROJECT}/deployments"


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
    # Step 0: Load manifest
    if not os.path.exists(MANIFEST_FILE):
        sys.exit(f"ERROR: manifest not found at {MANIFEST_FILE}. Run: node compute_blake3.js")
    with open(MANIFEST_FILE) as f:
        manifest_data = json.load(f)
    # manifest_data: {"/index.html": {"hash": "...", "size": 123}}
    # Build the deploy manifest format expected by Cloudflare: {"/index.html": "hash"}
    deploy_manifest = {path: info["hash"] for path, info in manifest_data.items()}
    print(f"== Loaded manifest: {len(deploy_manifest)} entries ==")

    # Step 1: Build asset upload payload (only for files that need uploading)
    assets = []
    for path, info in sorted(manifest_data.items()):
        rel = path.lstrip("/")  # remove leading slash for local path
        full = os.path.join(SITE_DIR, rel)
        if not os.path.exists(full):
            sys.exit(f"ERROR: file not found: {full}")
        with open(full, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ct, _ = mimetypes.guess_type(full)
        assets.append({
            "key": info["hash"],
            "value": b64,
            "base64": True,
            "metadata": {"contentType": ct or "application/octet-stream"},
        })

    # Step 2: Upload assets in batches (max ~200KB per batch payload)
    MAX = 200 * 1024
    batches = []
    batch, batch_size = [], 0
    for a in assets:
        sz = len(a["value"])
        if batch and batch_size + sz > MAX:
            batches.append(batch); batch, batch_size = [], 0
        batch.append(a); batch_size += sz
    if batch:
        batches.append(batch)

    print(f"\n== Step 1: upload {len(assets)} assets in {len(batches)} batch(es) ==")
    for i, b in enumerate(batches):
        payload = json.dumps(b)
        status, body = http_call(UPLOAD_URL, method="POST", data=payload, headers={
            "Authorization": f"Bearer {JWT}",
            "Content-Type": "application/json",
        })
        ok = (200 <= status < 300)
        print(f"  batch {i+1}/{len(batches)}: HTTP {status} ({len(payload)} bytes) {'OK' if ok else 'FAIL'}")
        if not ok:
            print(f"    response: {body[:500]}")
            sys.exit(f"upload batch {i+1} failed")
        # Show which assets were accepted/skipped
        try:
            r = json.loads(body)
            result = r.get("result", {})
            if "keys" in result:
                keys_status = result.get("keys", {})
                if isinstance(keys_status, list):
                    skipped = sum(1 for k in keys_status if not k.get("exists", False))
                    print(f"    {len(keys_status)} keys, {skipped} already exist (skipped)")
        except Exception:
            pass

    # Step 3: Upsert hashes (JWT works for this endpoint)
    print(f"\n== Step 2: upsert hashes ==")
    hashes_list = [info["hash"] for info in manifest_data.values()]
    upsert_body = json.dumps({"hashes": hashes_list}).encode()
    status, body = http_call(f"{API}/pages/assets/upsert-hashes", method="POST",
                             data=upsert_body, headers={
        "Authorization": f"Bearer {JWT}",
        "Content-Type": "application/json",
    })
    print(f"  HTTP {status}")
    print(f"  response: {body[:400]}")
    # Continue even if upsert fails (wrangler treats it as best-effort)
    if not (200 <= status < 300):
        print(f"  (upsert failed - continuing anyway, this is best-effort)")

    # Save manifest to a file so MCP can create the deployment
    deploy_manifest_path = "/workspace/deploy_manifest.json"
    with open(deploy_manifest_path, "w") as f:
        json.dump(deploy_manifest, f)
    print(f"\n== Manifest saved to {deploy_manifest_path} ==")
    print(f"== Now use MCP cloudflare execute to create the deployment (needs API token, not JWT) ==")
    print(f"== Manifest entries: {len(deploy_manifest)} files ==")


if __name__ == "__main__":
    main()
