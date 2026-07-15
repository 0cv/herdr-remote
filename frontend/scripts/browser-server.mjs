import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import { createServer } from 'node:http';

const root = resolve(process.argv[2] || 'dist');
const port = Number(process.env.PORT || 4173);
const types = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
};

createServer(async (request, response) => {
  const pathname = decodeURIComponent(new URL(request.url || '/', 'http://localhost').pathname);
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const file = resolve(root, relative);
  if (file !== root && !file.startsWith(`${root}${sep}`)) {
    response.writeHead(404).end('Not found\n');
    return;
  }
  const details = await stat(file).catch(() => null);
  if (!details?.isFile()) {
    response.writeHead(404).end('Not found\n');
    return;
  }
  response.writeHead(200, {
    'Cache-Control': 'no-cache',
    'Content-Type': types[extname(file)] || 'application/octet-stream',
    'X-Content-Type-Options': 'nosniff',
  });
  createReadStream(file).pipe(response);
}).listen(port, '127.0.0.1', () => {
  console.log(`Serving ${root} on http://127.0.0.1:${port}`);
});
