#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上传 site/ 目录所有文件到 Cloudflare Pages assets，输出 manifest JSON。"""
import os, sys, json, hashlib, base64, mimetypes, urllib.request, urllib.error

SITE_DIR = "/workspace/site"
UPLOAD_URL = "https://api.cloudflare.com/client/v4/pages/assets/upload"
JWT = os.environ["CF_JWT"]

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

# 1. 收集文件
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
                       "contentType": ct or "application/octet-stream"})
        manifest[logical] = h
        print(f"  {logical}  {h[:12]}…  {len(b64)} b64", flush=True)

# 2. 分批上传（每批 <= 240KB base64）
MAX = 240 * 1024
batch, batch_size = [], 0
batches = []
for a in assets:
    sz = len(a["value"])
    if batch and batch_size + sz > MAX:
        batches.append(batch); batch, batch_size = [], 0
    batch.append(a); batch_size += sz
if batch:
    batches.append(batch)

print(f"\n上传 {len(assets)} 个文件，分 {len(batches)} 批", flush=True)
for i, b in enumerate(batches):
    data = json.dumps(b).encode()
    req = urllib.request.Request(UPLOAD_URL, data=data, method="POST", headers={
        "Authorization": f"Bearer {JWT}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"  batch {i+1}/{len(batches)}: {'ok' if result.get('success') else 'FAIL'} ({len(b)} files)", flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  batch {i+1}: HTTP {e.code} {body[:200]}", flush=True)
        sys.exit(1)

# 3. 输出 manifest
with open("/workspace/cf_manifest.json", "w") as f:
    json.dump(manifest, f)
print(f"\nmanifest 写入 /workspace/cf_manifest.json ({len(manifest)} 条)")
