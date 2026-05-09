import { copyFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');
const dest = resolve(root, 'src/static/js');

const assets = [
    { from: 'node_modules/htmx.org/dist/htmx.min.js', to: 'htmx.min.js' },
    { from: 'node_modules/alpinejs/dist/cdn.min.js',   to: 'alpine.min.js' },
];

await mkdir(dest, { recursive: true });

for (const { from, to } of assets) {
    const src = resolve(root, from);
    const out = resolve(dest, to);
    await copyFile(src, out);
    console.log(`copied ${from} -> ${out}`);
}
