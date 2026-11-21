// Entry point for the news-image-20261121 submission.
//
// The finished front page ships in this repository as entry.png (produced
// by render_image.py from stories.json).  This program is the delivery
// step: it sanity-checks the shipped file — it must really be a PNG and
// stay within the competition's one-mebibyte cap — and then copies it to
// the output directory as entry.png.  Any failed check aborts with a
// non-zero exit code so a broken entry is never delivered silently.

import { copyFileSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SIZE_LIMIT_BYTES = 1_048_576; // 1 MiB
const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

function die(message: string): never {
  console.error(`main: ${message}`);
  process.exit(1);
}

function loadSource(): { path: string; bytes: Buffer } {
  const here = dirname(fileURLToPath(import.meta.url));
  const path = join(here, "entry.png");
  let bytes: Buffer;
  try {
    bytes = readFileSync(path);
  } catch {
    die(`cannot read shipped entry.png at ${path}`);
  }
  return { path, bytes };
}

function checkPng(bytes: Buffer): void {
  if (bytes.length === 0) {
    die("entry.png is empty");
  }
  if (bytes.length > SIZE_LIMIT_BYTES) {
    die(`entry.png is ${bytes.length} bytes, over the ${SIZE_LIMIT_BYTES}-byte limit`);
  }
  const head = [...bytes.subarray(0, PNG_SIGNATURE.length)];
  const isPng = PNG_SIGNATURE.every((byte, i) => head[i] === byte);
  if (!isPng) {
    die("entry.png does not start with the PNG signature bytes");
  }
}

function deliver(sourcePath: string): string {
  const outDir = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";
  mkdirSync(outDir, { recursive: true });
  const target = join(outDir, "entry.png");
  copyFileSync(sourcePath, target);
  const written = statSync(target).size;
  const expected = statSync(sourcePath).size;
  if (written !== expected) {
    die(`copy mismatch: wrote ${written} bytes, source has ${expected}`);
  }
  return target;
}

function main(): void {
  const { path, bytes } = loadSource();
  checkPng(bytes);
  const target = deliver(path);
  console.log(`main: delivered ${bytes.length} bytes to ${target}`);
}

main();
