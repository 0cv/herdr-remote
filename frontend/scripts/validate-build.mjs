import { readFile, readdir, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import versions from '../build-versions.json' with { type: 'json' };

const root = resolve(process.argv[2] || 'dist');
const required = [
  '_headers',
  'index.html',
  'manifest.webmanifest',
  'notification-icons.js',
  'sw.js',
  'assets/app.js',
  'assets/app.css',
  'icons/icon.svg',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/icon-maskable-512.png',
  'icons/apple-touch-icon.png',
];

for (const relative of required) {
  const file = join(root, relative);
  if (!(await stat(file).catch(() => null))?.isFile()) {
    throw new Error(`Required release file is missing: ${relative}`);
  }
}

const assets = await readdir(join(root, 'assets'));
const scripts = assets.filter((name) => name.endsWith('.js'));
const styles = assets.filter((name) => name.endsWith('.css'));
if (scripts.length !== 1 || scripts[0] !== 'app.js') {
  throw new Error(`Expected only assets/app.js; found ${scripts.join(', ')}`);
}
if (styles.length !== 1 || styles[0] !== 'app.css') {
  throw new Error(`Expected only assets/app.css; found ${styles.join(', ')}`);
}

const html = await readFile(join(root, 'index.html'), 'utf8');
for (const reference of [`assets/app.js?v=${versions.assets}`, `assets/app.css?v=${versions.assets}`]) {
  if (!html.includes(reference)) throw new Error(`index.html is missing ${reference}`);
}
if (/assets\/app\.(?:js|css)(?!\?v=)/.test(html)) {
  throw new Error('Application asset references must carry the manual cache-busting version');
}

const headers = await readFile(join(root, '_headers'), 'utf8');
for (const route of ['/sw.js', '/', '/index.html']) {
  const block = new RegExp(`(?:^|\\n)${route.replace('.', '\\.')}\\n(?:[ \\t]+[^\\n]+\\n)*[ \\t]+Cache-Control: no-cache(?:\\n|$)`);
  if (!block.test(headers)) throw new Error(`_headers does not preserve no-cache for ${route}`);
}

const serviceWorker = await readFile(join(root, 'sw.js'), 'utf8');
if (!serviceWorker.includes(`notification-icons.js?v=${versions.notificationIcons}`)) {
  throw new Error('sw.js notification icon version differs from build-versions.json');
}

const manifest = JSON.parse(await readFile(join(root, 'manifest.webmanifest'), 'utf8'));
if (manifest.start_url !== './' || manifest.scope !== './' || manifest.display !== 'standalone') {
  throw new Error('PWA manifest start_url, scope, or display contract changed');
}
if (!Array.isArray(manifest.icons) || manifest.icons.length < 3) {
  throw new Error('PWA manifest icons are incomplete');
}

console.log(`Validated release structure in ${root}`);
