const blake3Wasm = require('/root/.npm/_npx/32026684e21afda6/node_modules/blake3-wasm');
const fs = require('fs');
const path = require('path');

const SITE_DIR = '/workspace/site';

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
  for (const { full, relative } of files) {
    const contents = fs.readFileSync(full);
    const base64Contents = contents.toString('base64');
    const ext = path.extname(full).substring(1);
    const hash = blake3Wasm.hash(base64Contents + ext).toString('hex').slice(0, 32);
    const size = fs.statSync(full).size;
    // Normalize path: use forward slashes, no leading slash (wrangler convention)
    const normalized = relative.replace(/\\/g, '/');
    manifest[normalized] = { hash, size };
    console.log(`${normalized}\t${hash}\t${size}`);
  }
  
  // Save manifest to file
  fs.writeFileSync('/workspace/blake3_manifest.json', JSON.stringify(manifest, null, 2));
  console.log('\nManifest saved to /workspace/blake3_manifest.json');
}

main().catch(e => { console.error(e); process.exit(1); });
