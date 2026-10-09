// Compute BLAKE3 hashes for Cloudflare Pages assets
// Uses the same algorithm as wrangler: blake3(base64(contents) + extension).hex().slice(0, 32)
const fs = require('fs');
const path = require('path');
const blake3Wasm = require('blake3-wasm');

const SITE_DIR = '/workspace/site';
const MANIFEST_OUT = '/workspace/blake3_manifest.json';

async function main() {
  await blake3Wasm.ready;

  const files = [];
  function walk(dir, rel = '') {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      const relative = rel ? rel + '/' + entry.name : entry.name;
      if (entry.isDirectory()) {
        walk(full, relative);
      } else if (entry.isFile() && !entry.isSymbolicLink()) {
        files.push({ full, relative });
      }
    }
  }
  walk(SITE_DIR);
  files.sort((a, b) => a.relative.localeCompare(b.relative));

  const manifest = {};
  let totalSize = 0;
  for (const { full, relative } of files) {
    const contents = fs.readFileSync(full);
    const base64Contents = contents.toString('base64');
    const ext = path.extname(full).substring(1);
    // Wrangler algorithm: blake3Wasm.hash(base64 + ext).toString('hex').slice(0, 32)
    const hash = blake3Wasm.hash(base64Contents + ext).toString('hex').slice(0, 32);
    const size = fs.statSync(full).size;
    // Wrangler convention: leading slash, forward slashes
    const normalized = '/' + relative.replace(/\\/g, '/');
    manifest[normalized] = { hash, size };
    totalSize += size;
    console.log(`${normalized}\t${hash}\t${size}`);
  }

  fs.writeFileSync(MANIFEST_OUT, JSON.stringify(manifest, null, 2));
  console.log(`\nManifest saved to ${MANIFEST_OUT}`);
  console.log(`Total files: ${files.length}`);
  console.log(`Total size: ${totalSize} bytes`);
}

main().catch(e => { console.error(e); process.exit(1); });
