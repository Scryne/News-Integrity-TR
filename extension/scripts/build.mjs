// Bundles the extension into dist/ (load dist/ as an unpacked extension).
// NIT_BACKEND overrides the backend origin (default http://127.0.0.1:8765, ADR-014).
import { build } from "esbuild";
import { copyFileSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const backend = process.env.NIT_BACKEND ?? "http://127.0.0.1:8765";
if (!/^http:\/\/127\.0\.0\.1:\d{2,5}$/.test(backend)) {
  throw new Error(`NIT_BACKEND must be http://127.0.0.1:<port> (loopback only, ADR-014), got ${backend}`);
}

rmSync(dist, { recursive: true, force: true });
mkdirSync(join(dist, "icons"), { recursive: true });

await build({
  entryPoints: {
    content: join(root, "src/content/index.ts"),
    background: join(root, "src/background/index.ts"),
  },
  outdir: dist,
  bundle: true,
  format: "iife",
  target: "chrome116",
  charset: "utf8",
  legalComments: "none",
  define: { __NIT_BACKEND__: JSON.stringify(backend) },
  logLevel: "info",
});
copyFileSync(join(root, "static/manifest.json"), join(dist, "manifest.json"));

// Icon: a seal ring in the accent colour on the panel surface (DESIGN.md signature).
function crc32(buf) {
  let c, crc = 0xffffffff;
  for (let n = 0; n < buf.length; n++) {
    c = (crc ^ buf[n]) & 0xff;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crc = (crc >>> 8) ^ c;
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}
function icon(size) {
  const surface = [20, 22, 27], accent = [224, 105, 79];
  const rows = [];
  const c = (size - 1) / 2, outer = size * 0.46, ring = size * 0.1, dot = size * 0.13, corner = size * 0.22;
  for (let y = 0; y < size; y++) {
    const row = [0];
    for (let x = 0; x < size; x++) {
      // rounded-square tile
      const dx = Math.max(Math.abs(x - c) - (c - corner), 0), dy = Math.max(Math.abs(y - c) - (c - corner), 0);
      const inTile = Math.hypot(dx, dy) <= corner + 0.5;
      const d = Math.hypot(x - c, y - c);
      const onRing = d <= outer * 0.82 && d >= outer * 0.82 - ring;
      const onDot = d <= dot;
      const rgb = onRing || onDot ? accent : surface;
      row.push(...rgb, inTile ? 255 : 0);
    }
    rows.push(Buffer.from(row));
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0); header.writeUInt32BE(size, 4);
  header[8] = 8; header[9] = 6; header[10] = 0; header[11] = 0; header[12] = 0;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header), chunk("IDAT", deflateSync(Buffer.concat(rows))), chunk("IEND", Buffer.alloc(0)),
  ]);
}
for (const size of [16, 48, 128]) writeFileSync(join(dist, "icons", `icon-${size}.png`), icon(size));
console.log(`dist/ ready (backend ${backend})`);
